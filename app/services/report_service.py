"""Report lifecycle: upload -> OCR processing -> review (correct / validate) -> approval.

Access rules:
* operator-only users see and change only the reports they uploaded,
* viewer-only users can never change a report,
* role checks per endpoint are done in the routers (see app/api/deps.py).
"""

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import PurePath
from statistics import fmean

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.core.time import start_of_utc_day, utcnow
from app.db.pagination import count_rows, normalize_page
from app.models import (
    Department,
    OcrExtraction,
    Report,
    ReportFieldValue,
    ReportFile,
    ReportLine,
    ReportTemplate,
    TemplateField,
    User,
    ValidationHistory,
)
from app.models.enums import (
    AuditAction,
    EntityType,
    FieldScope,
    FieldValueStatus,
    HistoryAction,
    ReportFileKind,
    ReportStatus,
)
from app.schemas.common import PageResponse
from app.schemas.report import FieldDto, ReportDetail, ReportSummary
from app.services import audit_service, notification_service, ocr_client, settings_service, template_service
from app.services.field_validator import FieldCheck, check_value
from app.services.ocr_client import OcrField, OcrResponse, OcrServiceError
from app.services.report_status import transition
from app.storage.local import display_filename, get_storage, sanitize_filename
from app.storage.preview import PreviewError, render_preview_png

logger = logging.getLogger(__name__)

CONTENT_TYPE_BY_EXTENSION = {
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "tif": "image/tiff",
    "tiff": "image/tiff",
}
ALLOWED_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/jpg", "image/pjpeg", "image/png", "image/tiff", "image/tif"}
UNSUPPORTED_FILE_MESSAGE = "Only PDF, JPG, PNG and TIFF files are supported"

# Line fields used by the list filters (different templates name the same column differently).
SUPPLIER_KEYS = ("supplierName", "vendorName")
PART_KEYS = ("partName", "itemName")
PROBLEM_KEYS = ("problemDescription", "reasonRemarks")

MONTH_FIELD_KEY = "month"
DATE_FIELD_KEY = "date"


@dataclass(frozen=True)
class UploadedFile:
    filename: str
    content_type: str
    data: bytes


@dataclass(frozen=True)
class StoredFile:
    data: bytes
    content_type: str
    filename: str


@dataclass(frozen=True)
class ReportFilters:
    q: str | None = None
    template_id: int | None = None
    status: ReportStatus | None = None
    uploaded_by: int | None = None
    supplier: str | None = None
    part: str | None = None
    problem: str | None = None
    date_from: date | None = None
    date_to: date | None = None


# --------------------------------------------------------------------------- queries

def list_reports(db: Session, user: User, filters: ReportFilters, page: int, size: int) -> PageResponse[ReportSummary]:
    page, size = normalize_page(page, size)
    conditions = []

    if user.is_operator_only:
        conditions.append(Report.uploaded_by_id == user.id)  # uploadedBy filter is ignored for operators
    elif filters.uploaded_by is not None:
        conditions.append(Report.uploaded_by_id == filters.uploaded_by)

    if filters.q and filters.q.strip():
        term = filters.q.strip()
        conditions.append(
            Report.document_name.icontains(term, autoescape=True)
            | Report.template.has(ReportTemplate.name.icontains(term, autoescape=True))
            | Report.report_month.icontains(term, autoescape=True)
        )
    if filters.template_id is not None:
        conditions.append(Report.template_id == filters.template_id)
    if filters.status is not None:
        conditions.append(Report.status == filters.status)
    for keys, text in ((SUPPLIER_KEYS, filters.supplier), (PART_KEYS, filters.part), (PROBLEM_KEYS, filters.problem)):
        if text and text.strip():
            conditions.append(_has_line_value(keys, text.strip()))
    if filters.date_from:
        conditions.append(Report.created_at >= start_of_utc_day(filters.date_from))
    if filters.date_to:
        conditions.append(Report.created_at < start_of_utc_day(filters.date_to) + timedelta(days=1))

    stmt = select(Report).where(*conditions).order_by(Report.created_at.desc(), Report.id.desc())
    total = count_rows(db, stmt)
    reports = db.scalars(stmt.offset(page * size).limit(size)).all()
    return PageResponse[ReportSummary].of([ReportSummary.from_model(r) for r in reports], page=page, size=size, total=total)


def get_report_detail(db: Session, user: User, report_id: int) -> ReportDetail:
    report = _get_report(db, report_id)
    _ensure_can_view(report, user)
    return ReportDetail.from_model(report, _field_values(db, report.id))


def get_extractions(db: Session, user: User, report_id: int) -> list[str]:
    report = _get_report(db, report_id)
    _ensure_can_view(report, user)
    responses = db.scalars(
        select(OcrExtraction.raw_response)
        .where(OcrExtraction.report_id == report.id)
        .order_by(OcrExtraction.created_at.desc(), OcrExtraction.id.desc())
    )
    return [json.dumps(raw, ensure_ascii=False) for raw in responses]


def get_report_file(db: Session, user: User, report_id: int, kind: ReportFileKind) -> StoredFile:
    report = _get_report(db, report_id)
    _ensure_can_view(report, user)
    stored = db.scalar(select(ReportFile).where(ReportFile.report_id == report.id, ReportFile.kind == kind))
    if stored is None:
        raise NotFoundError("Preview not available" if kind == ReportFileKind.PREVIEW else "File not found")
    try:
        data = get_storage().read(stored.storage_key)
    except FileNotFoundError:
        logger.error("Report %s: stored file %s is missing from disk", report.id, stored.storage_key)
        raise NotFoundError("The stored file is missing. Please upload the report again.") from None
    return StoredFile(data=data, content_type=stored.content_type, filename=stored.original_filename)


# --------------------------------------------------------------------------- upload

def upload_report(db: Session, user: User, template_id: int, department_id: int | None, upload: UploadedFile) -> ReportSummary:
    extension = _validate_upload(upload)

    template = db.get(ReportTemplate, template_id)
    if template is None:
        raise NotFoundError("Report template not found")
    if not template.active:
        raise BadRequestError("This report template is not active")
    if department_id is not None and db.get(Department, department_id) is None:
        raise NotFoundError("Department not found")

    try:
        preview_png = render_preview_png(upload.data, extension)
    except PreviewError as exc:
        logger.info("Rejected upload %r: %s", upload.filename, exc)
        raise BadRequestError("We could not open this file. Please upload a clear PDF or image.") from exc

    name = display_filename(upload.filename)
    folder = uuid.uuid4().hex
    original_key = f"{folder}/{sanitize_filename(name)}"
    preview_key = f"{folder}/preview.png"

    report = Report(
        template=template,
        department_id=department_id,
        uploader=user,
        document_name=name,
        original_filename=name,
        status=ReportStatus.UPLOADED,
        files=[
            ReportFile(
                kind=ReportFileKind.ORIGINAL,
                storage_key=original_key,
                content_type=CONTENT_TYPE_BY_EXTENSION[extension],
                size_bytes=len(upload.data),
                original_filename=name,
            ),
            ReportFile(
                kind=ReportFileKind.PREVIEW,
                storage_key=preview_key,
                content_type="image/png",
                size_bytes=len(preview_png),
                original_filename="preview.png",
            ),
        ],
    )
    db.add(report)
    db.flush()  # assigns report.id
    audit_service.record(
        db, actor=user, action=AuditAction.REPORT_UPLOADED, entity_type=EntityType.REPORT, entity_id=report.id,
        details={"documentName": name, "templateCode": template.code},
    )

    storage = get_storage()
    try:
        storage.save(original_key, upload.data)
        storage.save(preview_key, preview_png)
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(original_key)
        storage.delete(preview_key)
        raise

    logger.info("Report %s uploaded by user %s (%s, %d bytes)", report.id, user.id, template.code, len(upload.data))
    return ReportSummary.from_model(report)


def _validate_upload(upload: UploadedFile) -> str:
    """Returns the file extension (pdf, jpg, ...) or raises BadRequestError."""
    if not upload.data:
        raise BadRequestError("The uploaded file is empty")
    if len(upload.data) > settings.MAX_UPLOAD_BYTES:
        raise BadRequestError(f"The file is too large. The maximum size is {settings.MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    extension = PurePath(display_filename(upload.filename)).suffix.lower().lstrip(".")
    if extension not in CONTENT_TYPE_BY_EXTENSION:
        raise BadRequestError(UNSUPPORTED_FILE_MESSAGE)
    content_type = (upload.content_type or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise BadRequestError(UNSUPPORTED_FILE_MESSAGE)
    return extension


# --------------------------------------------------------------------------- OCR processing

def process_report(db: Session, user: User, report_id: int) -> ReportDetail:
    """Run OCR on an UPLOADED or FAILED report. On any failure the report is marked FAILED and a 400 is returned."""
    report = _get_report(db, report_id, for_update=True)
    _ensure_can_modify(report, user)
    if report.status not in (ReportStatus.UPLOADED, ReportStatus.FAILED):
        raise ConflictError("Only uploaded or failed reports can be processed")

    # Step 1, in its own transaction: everyone can now see the report is being processed.
    transition(report, ReportStatus.PROCESSING)
    report.failure_reason = None
    db.commit()

    try:
        original = _report_file(report, ReportFileKind.ORIGINAL)
        content = get_storage().read(original.storage_key)
        ocr = ocr_client.extract(
            content=content,
            filename=original.original_filename,
            content_type=original.content_type,
            template=template_service.build_ocr_payload(report.template),
        )
        _save_ocr_result(db, report, ocr)
        db.commit()
    except Exception as exc:
        db.rollback()
        reason, user_message = _describe_processing_failure(exc)
        logger.warning("Processing report %s failed: %s", report_id, reason, exc_info=not isinstance(exc, OcrServiceError))
        _mark_failed(db, report_id, user, reason)
        raise BadRequestError(user_message) from exc

    logger.info("Report %s processed: %s", report.id, report.status)
    return get_report_detail(db, user, report.id)


def _save_ocr_result(db: Session, report: Report, ocr: OcrResponse) -> None:
    # Clear the results of any previous run.
    db.execute(delete(ReportFieldValue).where(ReportFieldValue.report_id == report.id))
    db.execute(delete(ReportLine).where(ReportLine.report_id == report.id))

    template_fields = {field.field_key: field for field in report.template.fields}
    verified_threshold, review_threshold = settings_service.ocr_thresholds(db)
    lines: dict[int, ReportLine] = {}
    seen: set[tuple[str, int | None]] = set()
    confidences: list[float] = []
    report_month: str | None = None
    first_date: tuple[int, date] | None = None  # (row index, date)

    for ocr_field in ocr.result.fields:
        template_field = template_fields.get(ocr_field.field_name)
        if template_field is None:
            logger.warning("Report %s: OCR returned unknown field %r; ignored", report.id, ocr_field.field_name)
            continue

        is_line = template_field.scope == FieldScope.LINE
        row_index = (ocr_field.row_index or 0) if is_line else None
        if (template_field.field_key, row_index) in seen:
            logger.warning("Report %s: duplicate OCR value for %s row %s; ignored", report.id, template_field.field_key, row_index)
            continue
        seen.add((template_field.field_key, row_index))

        line = None
        if is_line:
            line = lines.get(row_index)
            if line is None:
                line = lines[row_index] = ReportLine(report_id=report.id, row_index=row_index)
                db.add(line)

        value = _as_text(ocr_field.value)
        check = check_value(template_field.data_type, template_field.required, value)
        db.add(
            ReportFieldValue(
                report_id=report.id,
                template_field=template_field,
                line=line,
                raw_value=_as_text(ocr_field.raw_value),
                original_value=value,
                numeric_value=check.numeric_value,
                confidence=ocr_field.confidence,
                status=_status_after_ocr(value, template_field.required, check, ocr_field.confidence, verified_threshold, review_threshold),
                page_index=ocr_field.page_index or 0,
                **_bounding_box_columns(ocr_field),
            )
        )

        if ocr_field.confidence is not None:
            confidences.append(ocr_field.confidence)
        if template_field.field_key == MONTH_FIELD_KEY and not is_line and value:
            report_month = check.month_label or value
        if template_field.field_key == DATE_FIELD_KEY and is_line and check.date_value:
            if first_date is None or row_index < first_date[0]:
                first_date = (row_index, check.date_value)

    # Header/footer fields the OCR service did not return still get a row, so reviewers can fill them in.
    for template_field in report.template.fields:
        if template_field.scope != FieldScope.LINE and (template_field.field_key, None) not in seen:
            db.add(
                ReportFieldValue(
                    report_id=report.id,
                    template_field=template_field,
                    status=FieldValueStatus.ERROR if template_field.required else FieldValueStatus.EMPTY,
                )
            )

    report.report_month = report_month
    report.report_date = first_date[1] if first_date else None
    report.average_confidence = round(fmean(confidences), 4) if confidences else None
    db.add(OcrExtraction(report_id=report.id, engine=ocr.result.engine, raw_response=ocr.raw))

    transition(report, ReportStatus.OCR_COMPLETED)
    transition(report, ReportStatus.VALIDATION_REQUIRED)
    notification_service.notify(
        db,
        user_id=report.uploaded_by_id,
        title="Report ready for review",
        body=f"{report.document_name} has been read and needs validation.",
    )
    audit_service.record(
        db, actor=None, action=AuditAction.REPORT_PROCESSED, entity_type=EntityType.REPORT, entity_id=report.id,
        details={"fields": len(seen), "rows": len(lines), "averageConfidence": report.average_confidence},
    )


def _status_after_ocr(
    value: str | None, required: bool, check: FieldCheck, confidence: float | None, verified: float, review: float
) -> FieldValueStatus:
    if not (value or "").strip():
        return FieldValueStatus.ERROR if required else FieldValueStatus.EMPTY
    if not check.ok:
        return FieldValueStatus.ERROR
    score = confidence or 0.0
    if score >= verified:
        return FieldValueStatus.VERIFIED
    if score >= review:
        return FieldValueStatus.NEEDS_REVIEW
    return FieldValueStatus.ERROR


def _mark_failed(db: Session, report_id: int, user: User, reason: str) -> None:
    report = _get_report(db, report_id)
    transition(report, ReportStatus.FAILED)
    report.failure_reason = reason[:2000]
    audit_service.record(
        db, actor=user, action=AuditAction.REPORT_PROCESSING_FAILED, entity_type=EntityType.REPORT, entity_id=report.id,
        details={"reason": report.failure_reason},
    )
    db.commit()


def _describe_processing_failure(exc: Exception) -> tuple[str, str]:
    """(reason stored on the report, message shown to the user)."""
    if isinstance(exc, OcrServiceError):
        return exc.reason, exc.user_message
    if isinstance(exc, FileNotFoundError):
        return "Original file is missing from storage", "The uploaded file could not be found. Please upload it again."
    return f"Unexpected error: {type(exc).__name__}: {exc}", "We could not process this report. Please try again."


# --------------------------------------------------------------------------- review

def correct_field(db: Session, user: User, report_id: int, field_id: int, new_value: str | None) -> FieldDto:
    report = _get_report(db, report_id, for_update=True)
    _ensure_can_modify(report, user)
    _ensure_reviewable(report)

    field = db.scalar(select(ReportFieldValue).where(ReportFieldValue.id == field_id, ReportFieldValue.report_id == report.id))
    if field is None:
        raise NotFoundError("Field not found on this report")

    template_field = field.template_field
    value = (new_value or "").strip()
    check = check_value(template_field.data_type, template_field.required, value)
    if value and not check.ok:
        raise BadRequestError(f"{template_field.label} {check.error}")

    old_value = field.effective_value
    field.corrected_value = value
    field.numeric_value = check.numeric_value
    field.corrected_by_id = user.id
    field.corrector = user
    field.corrected_at = utcnow()
    field.status = FieldValueStatus.ERROR if (template_field.required and not value) else FieldValueStatus.VERIFIED

    if report.status == ReportStatus.VALIDATED:
        transition(report, ReportStatus.VALIDATION_REQUIRED)  # a changed report must be validated again
    _add_history(db, report, user, HistoryAction.CORRECTED, field_value_id=field.id, old_value=old_value, new_value=value)
    db.commit()
    return FieldDto.from_model(field)


def validate_report(db: Session, user: User, report_id: int) -> ReportDetail:
    report = _get_report(db, report_id, for_update=True)
    _ensure_can_modify(report, user)
    _ensure_reviewable(report)

    problems = []
    has_table_row = False
    for field in _field_values(db, report.id):
        template_field = field.template_field
        if template_field.scope == FieldScope.FOOTER:
            continue
        if template_field.scope == FieldScope.LINE and field.line_id is not None:
            has_table_row = True
        check = check_value(template_field.data_type, template_field.required, field.effective_value)
        if not check.ok:
            prefix = f"Row {field.line.row_index + 1}: " if field.line else ""
            problems.append(f"{prefix}{template_field.label} {check.error}")
    if not has_table_row:
        problems.append("The report has no table rows. At least one row is required.")
    if problems:
        raise BadRequestError("Some fields need attention before this report can be validated", details=problems)

    if report.status == ReportStatus.VALIDATION_REQUIRED:
        transition(report, ReportStatus.VALIDATED)
    _add_history(db, report, user, HistoryAction.VALIDATED)
    audit_service.record(db, actor=user, action=AuditAction.REPORT_VALIDATED, entity_type=EntityType.REPORT, entity_id=report.id)
    db.commit()
    return get_report_detail(db, user, report.id)


def approve_report(db: Session, user: User, report_id: int) -> ReportDetail:
    report = _get_report(db, report_id, for_update=True)
    _ensure_can_modify(report, user)
    if report.status != ReportStatus.VALIDATED:
        raise ConflictError("Only validated reports can be approved")

    transition(report, ReportStatus.APPROVED)
    report.approver = user
    report.approved_at = utcnow()
    _add_history(db, report, user, HistoryAction.APPROVED)
    audit_service.record(db, actor=user, action=AuditAction.REPORT_APPROVED, entity_type=EntityType.REPORT, entity_id=report.id)
    db.commit()
    return get_report_detail(db, user, report.id)


# --------------------------------------------------------------------------- helpers

def _get_report(db: Session, report_id: int, *, for_update: bool = False) -> Report:
    report = db.get(Report, report_id, with_for_update=for_update)
    if report is None:
        raise NotFoundError("Report not found")
    return report


def _field_values(db: Session, report_id: int) -> list[ReportFieldValue]:
    return list(db.scalars(select(ReportFieldValue).where(ReportFieldValue.report_id == report_id)))


def _report_file(report: Report, kind: ReportFileKind) -> ReportFile:
    for stored in report.files:
        if stored.kind == kind:
            return stored
    raise FileNotFoundError(f"Report {report.id} has no {kind} file")


def _ensure_can_view(report: Report, user: User) -> None:
    if user.is_operator_only and report.uploaded_by_id != user.id:
        raise ForbiddenError("You can only review reports you uploaded")


def _ensure_can_modify(report: Report, user: User) -> None:
    if user.is_viewer_only:
        raise ForbiddenError("Viewers cannot change reports")
    _ensure_can_view(report, user)


def _ensure_reviewable(report: Report) -> None:
    if report.status == ReportStatus.APPROVED:
        raise ConflictError("Approved reports cannot be changed")
    if report.status not in (ReportStatus.VALIDATION_REQUIRED, ReportStatus.VALIDATED):
        raise ConflictError("This report has not been processed yet")


def _add_history(
    db: Session, report: Report, user: User, action: HistoryAction, *,
    field_value_id: int | None = None, old_value: str | None = None, new_value: str | None = None,
) -> None:
    db.add(
        ValidationHistory(
            report_id=report.id, field_value_id=field_value_id, action=action,
            old_value=old_value, new_value=new_value, actor_id=user.id,
        )
    )


def _has_line_value(field_keys: tuple[str, ...], text: str):
    """EXISTS: the report has a line field (one of field_keys) whose value contains text."""
    return (
        select(ReportFieldValue.id)
        .join(TemplateField, TemplateField.id == ReportFieldValue.template_field_id)
        .where(
            ReportFieldValue.report_id == Report.id,
            TemplateField.field_key.in_(field_keys),
            effective_value().icontains(text, autoescape=True),
        )
        .exists()
    )


def effective_value():
    """SQL expression for the value users see: the correction if set, otherwise the OCR value."""
    return func.coalesce(ReportFieldValue.corrected_value, ReportFieldValue.original_value)


def _as_text(value) -> str | None:
    """OCR values may arrive as strings or numbers; store them as text (2700.0 -> "2700")."""
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _bounding_box_columns(ocr_field: OcrField) -> dict:
    box = ocr_field.bounding_box
    if box is None:
        return {}
    return {"bbox_x": box.x, "bbox_y": box.y, "bbox_width": box.width, "bbox_height": box.height}

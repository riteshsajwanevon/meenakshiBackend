from datetime import date
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, UploadFile

from app.api.deps import CurrentUser, DbSession, ReviewerUser, UploaderUser
from app.api.responses import file_response
from app.core.config import settings
from app.core.errors import BadRequestError
from app.models.enums import ReportFileKind, ReportStatus
from app.schemas.common import PageResponse
from app.schemas.report import FieldCorrectionRequest, FieldDto, ReportDetail, ReportSummary
from app.services import export_service, report_service
from app.services.report_service import ReportFilters, UploadedFile

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("", response_model=PageResponse[ReportSummary])
def list_reports(
    db: DbSession,
    user: CurrentUser,
    q: str | None = None,
    template_id: Annotated[int | None, Query(alias="templateId")] = None,
    status: ReportStatus | None = None,
    uploaded_by: Annotated[int | None, Query(alias="uploadedBy")] = None,
    supplier: str | None = None,
    part: str | None = None,
    problem: str | None = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    page: int = 0,
    size: int = 10,
):
    filters = ReportFilters(
        q=q, template_id=template_id, status=status, uploaded_by=uploaded_by,
        supplier=supplier, part=part, problem=problem, date_from=date_from, date_to=date_to,
    )
    return report_service.list_reports(db, user, filters, page, size)


@router.post("", response_model=ReportSummary)
def upload_report(
    db: DbSession,
    user: UploaderUser,
    file: Annotated[UploadFile, File(description="PDF, JPG, PNG or TIFF")],
    template_id: Annotated[int, Form(alias="templateId")],
    department_id: Annotated[str | None, Form(alias="departmentId")] = None,
):
    upload = UploadedFile(
        filename=file.filename or "",
        content_type=file.content_type or "",
        data=file.file.read(settings.MAX_UPLOAD_BYTES + 1),  # one extra byte is enough to detect "too large"
    )
    return report_service.upload_report(db, user, template_id, _optional_int(department_id, "departmentId"), upload)


@router.get("/{report_id}", response_model=ReportDetail)
def get_report(report_id: int, db: DbSession, user: CurrentUser):
    return report_service.get_report_detail(db, user, report_id)


@router.post("/{report_id}/process", response_model=ReportDetail)
def process_report(report_id: int, db: DbSession, user: UploaderUser):
    return report_service.process_report(db, user, report_id)


@router.get("/{report_id}/extractions", response_model=list[str])
def get_extractions(report_id: int, db: DbSession, user: CurrentUser):
    return report_service.get_extractions(db, user, report_id)


@router.patch("/{report_id}/fields/{field_id}", response_model=FieldDto)
def correct_field(report_id: int, field_id: int, body: FieldCorrectionRequest, db: DbSession, user: ReviewerUser):
    return report_service.correct_field(db, user, report_id, field_id, body.value)


@router.post("/{report_id}/validate", response_model=ReportDetail)
def validate_report(report_id: int, db: DbSession, user: ReviewerUser):
    return report_service.validate_report(db, user, report_id)


@router.post("/{report_id}/approve", response_model=ReportDetail)
def approve_report(report_id: int, db: DbSession, user: ReviewerUser):
    return report_service.approve_report(db, user, report_id)


@router.get("/{report_id}/preview", responses={200: {"content": {"image/png": {}}}})
def get_preview(report_id: int, db: DbSession, user: CurrentUser):
    stored = report_service.get_report_file(db, user, report_id, ReportFileKind.PREVIEW)
    return file_response(stored.data, stored.content_type, f"report-{report_id}-preview.png", "inline")


@router.get("/{report_id}/file")
def get_original_file(report_id: int, db: DbSession, user: CurrentUser):
    stored = report_service.get_report_file(db, user, report_id, ReportFileKind.ORIGINAL)
    return file_response(stored.data, stored.content_type, stored.filename, "inline")


@router.get("/{report_id}/export")
def export_report(
    report_id: int,
    db: DbSession,
    user: CurrentUser,
    export_format: Annotated[str, Query(alias="format", description="xlsx | excel | csv | pdf")] = "xlsx",
):
    detail = report_service.get_report_detail(db, user, report_id)
    exported = export_service.export_report(detail, export_format)
    return file_response(exported.data, exported.content_type, exported.filename, "attachment")


def _optional_int(value: str | None, name: str) -> int | None:
    """Multipart forms often send optional numbers as an empty string."""
    if value is None or not value.strip():
        return None
    try:
        return int(value)
    except ValueError:
        raise BadRequestError("Validation failed", details=[f"{name}: must be a number"]) from None

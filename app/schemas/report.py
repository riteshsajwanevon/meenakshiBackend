from datetime import date, datetime

from pydantic import Field

from app.models import Report, ReportFieldValue
from app.models.enums import FieldDataType, FieldScope, FieldValueStatus, ReportStatus
from app.schemas.common import ApiModel

_SCOPE_ORDER = {FieldScope.HEADER: 0, FieldScope.LINE: 1, FieldScope.FOOTER: 2}


class BoundingBox(ApiModel):
    x: float
    y: float
    width: float
    height: float


class FieldDto(ApiModel):
    id: int
    line_id: int | None
    row_index: int | None
    field_key: str
    label: str
    scope: FieldScope
    data_type: FieldDataType
    required: bool
    raw_value: str | None
    original_value: str | None
    corrected_value: str | None
    value: str | None  # effective value: the correction if set, otherwise the OCR value
    confidence: float | None
    status: FieldValueStatus
    bounding_box: BoundingBox | None
    page_index: int
    corrected_by: str | None
    corrected_at: datetime | None

    @classmethod
    def from_model(cls, field: ReportFieldValue) -> "FieldDto":
        template_field = field.template_field
        has_box = None not in (field.bbox_x, field.bbox_y, field.bbox_width, field.bbox_height)
        return cls(
            id=field.id,
            line_id=field.line_id,
            row_index=field.line.row_index if field.line else None,
            field_key=template_field.field_key,
            label=template_field.label,
            scope=template_field.scope,
            data_type=template_field.data_type,
            required=template_field.required,
            raw_value=field.raw_value,
            original_value=field.original_value,
            corrected_value=field.corrected_value,
            value=field.effective_value,
            confidence=field.confidence,
            status=field.status,
            bounding_box=BoundingBox(x=field.bbox_x, y=field.bbox_y, width=field.bbox_width, height=field.bbox_height)
            if has_box
            else None,
            page_index=field.page_index,
            corrected_by=field.corrector.full_name if field.corrector else None,
            corrected_at=field.corrected_at,
        )


class ReportSummary(ApiModel):
    id: int
    document_name: str
    report_type: str
    template_code: str
    report_date: date | None
    report_month: str | None
    uploaded_at: datetime
    uploaded_by: str
    status: ReportStatus
    average_confidence: float | None
    department: str | None

    @classmethod
    def from_model(cls, report: Report) -> "ReportSummary":
        return cls(
            id=report.id,
            document_name=report.document_name,
            report_type=report.template.name,
            template_code=report.template.code,
            report_date=report.report_date,
            report_month=report.report_month,
            uploaded_at=report.created_at,
            uploaded_by=report.uploader.full_name,
            status=report.status,
            average_confidence=report.average_confidence,
            department=report.department.name if report.department else None,
        )


class ReportDetail(ApiModel):
    id: int
    document_name: str
    original_filename: str
    report_type: str
    template_code: str
    template_id: int
    department: str | None
    department_id: int | None
    status: ReportStatus
    report_month: str | None
    report_date: date | None
    average_confidence: float | None
    failure_reason: str | None
    uploaded_by: str
    uploaded_at: datetime
    approved_by: str | None
    approved_at: datetime | None
    preview_url: str
    fields: list[FieldDto]

    @classmethod
    def from_model(cls, report: Report, field_values: list[ReportFieldValue]) -> "ReportDetail":
        ordered = sorted(field_values, key=_display_order)
        return cls(
            id=report.id,
            document_name=report.document_name,
            original_filename=report.original_filename,
            report_type=report.template.name,
            template_code=report.template.code,
            template_id=report.template_id,
            department=report.department.name if report.department else None,
            department_id=report.department_id,
            status=report.status,
            report_month=report.report_month,
            report_date=report.report_date,
            average_confidence=report.average_confidence,
            failure_reason=report.failure_reason,
            uploaded_by=report.uploader.full_name,
            uploaded_at=report.created_at,
            approved_by=report.approver.full_name if report.approver else None,
            approved_at=report.approved_at,
            preview_url=f"/api/v1/reports/{report.id}/preview",
            fields=[FieldDto.from_model(field) for field in ordered],
        )


def _display_order(field: ReportFieldValue) -> tuple:
    """Header fields first, then table rows in order (columns left to right), then footer fields."""
    template_field = field.template_field
    row_index = field.line.row_index if field.line else -1
    return (_SCOPE_ORDER[template_field.scope], row_index, template_field.column_order, field.id)


class FieldCorrectionRequest(ApiModel):
    value: str | None = Field(default=None, max_length=2000)

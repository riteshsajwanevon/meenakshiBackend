"""Dashboard aggregates. Failed reports are excluded from every quantity."""

from datetime import timedelta

from sqlalchemy import desc, func, literal_column, select
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError
from app.core.time import utcnow
from app.models import Report, ReportFieldValue, ReportTemplate, TemplateField
from app.models.enums import ReportStatus
from app.schemas.misc import DashboardSummary, NameQuantity, TrendPoint
from app.services.report_service import PROBLEM_KEYS, SUPPLIER_KEYS, effective_value

TOP_GROUPS_LIMIT = 20
TREND_DAYS = 180
TREND_UNITS = {"daily": "day", "weekly": "week", "monthly": "month"}

# Which dashboard total each template's quantity field counts towards.
QUANTITY_BUCKET_BY_TEMPLATE = {
    "SUPPLIER_REJECTION": "rejection",
    "SUPPLIER_LOT_REJECTION_SUMMARY": "rejection",
    "SUPPLIER_REWORK": "rework",
    "SUPPLIER_SEGREGATION": "segregation",
    "SCRAP_NOTE": "scrap",
}


def _quantity_values(*columns):
    """SELECT columns FROM field values holding their template's quantity (e.g. rejectionQty), for non-failed reports."""
    return (
        select(*columns)
        .select_from(ReportFieldValue)
        .join(TemplateField, TemplateField.id == ReportFieldValue.template_field_id)
        .join(Report, Report.id == ReportFieldValue.report_id)
        .join(ReportTemplate, ReportTemplate.id == Report.template_id)
        .where(TemplateField.field_key == ReportTemplate.quantity_field_key, Report.status != ReportStatus.FAILED)
    )


def summary(db: Session) -> DashboardSummary:
    counts = dict(db.execute(select(Report.status, func.count()).group_by(Report.status)).all())

    quantities = {"rejection": 0.0, "rework": 0.0, "segregation": 0.0, "scrap": 0.0}
    per_template = _quantity_values(
        ReportTemplate.code, func.coalesce(func.sum(ReportFieldValue.numeric_value), 0)
    ).group_by(ReportTemplate.code)
    for template_code, quantity in db.execute(per_template):
        if bucket := QUANTITY_BUCKET_BY_TEMPLATE.get(template_code):
            quantities[bucket] += float(quantity)

    return DashboardSummary(
        total_reports=sum(counts.values()),
        pending_validation=counts.get(ReportStatus.VALIDATION_REQUIRED, 0),
        validated_reports=counts.get(ReportStatus.VALIDATED, 0),
        approved_reports=counts.get(ReportStatus.APPROVED, 0),
        processing=counts.get(ReportStatus.PROCESSING, 0) + counts.get(ReportStatus.OCR_COMPLETED, 0),
        failed=counts.get(ReportStatus.FAILED, 0),
        rejection_quantity=quantities["rejection"],
        rework_quantity=quantities["rework"],
        segregation_quantity=quantities["segregation"],
        scrap_quantity=quantities["scrap"],
    )


def top_rejection_reasons(db: Session) -> list[NameQuantity]:
    return _top_line_groups(db, PROBLEM_KEYS)


def top_suppliers(db: Session) -> list[NameQuantity]:
    return _top_line_groups(db, SUPPLIER_KEYS)


def _top_line_groups(db: Session, field_keys: tuple[str, ...]) -> list[NameQuantity]:
    """Group table rows by a text column (e.g. supplier name, case-insensitive) and sum each row's quantity."""
    quantity_per_line = (
        _quantity_values(ReportFieldValue.line_id.label("line_id"), ReportFieldValue.numeric_value.label("quantity"))
        .where(ReportFieldValue.line_id.is_not(None))
        .subquery()
    )
    label = func.trim(effective_value())
    stmt = (
        select(
            func.min(label).label("name"),
            func.coalesce(func.sum(quantity_per_line.c.quantity), 0).label("quantity"),
            func.count(ReportFieldValue.id).label("count"),
        )
        .select_from(ReportFieldValue)
        .join(TemplateField, TemplateField.id == ReportFieldValue.template_field_id)
        .join(Report, Report.id == ReportFieldValue.report_id)
        .outerjoin(quantity_per_line, quantity_per_line.c.line_id == ReportFieldValue.line_id)
        .where(
            TemplateField.field_key.in_(field_keys),
            ReportFieldValue.line_id.is_not(None),
            Report.status != ReportStatus.FAILED,
            label != "",
        )
        .group_by(func.lower(label))
        .order_by(desc("quantity"), desc("count"))
        .limit(TOP_GROUPS_LIMIT)
    )
    return [NameQuantity(name=name, quantity=float(quantity), count=count) for name, quantity, count in db.execute(stmt)]


def trends(db: Session, granularity: str) -> list[TrendPoint]:
    unit = TREND_UNITS.get((granularity or "daily").strip().lower())
    if unit is None:
        raise BadRequestError("granularity must be daily, weekly or monthly")

    quantity_per_report = (
        _quantity_values(ReportFieldValue.report_id.label("report_id"), func.sum(ReportFieldValue.numeric_value).label("quantity"))
        .group_by(ReportFieldValue.report_id)
        .subquery()
    )
    # A literal unit (not a bind parameter) so PostgreSQL sees SELECT and GROUP BY as the same expression.
    bucket = func.date_trunc(literal_column(f"'{unit}'"), Report.created_at)
    stmt = (
        select(bucket.label("bucket"), func.count(Report.id), func.coalesce(func.sum(quantity_per_report.c.quantity), 0))
        .select_from(Report)
        .outerjoin(quantity_per_report, quantity_per_report.c.report_id == Report.id)
        .where(Report.created_at >= utcnow() - timedelta(days=TREND_DAYS), Report.status != ReportStatus.FAILED)
        .group_by(bucket)
        .order_by(bucket)
    )
    return [
        TrendPoint(bucket=start.date().isoformat(), reports=reports, quantity=float(quantity))
        for start, reports, quantity in db.execute(stmt)
    ]

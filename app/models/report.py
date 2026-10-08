from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Float, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, BigIntPk, CreatedAtMixin, TimestampMixin, enum_column
from app.models.department import Department
from app.models.enums import FieldValueStatus, HistoryAction, ReportFileKind, ReportStatus
from app.models.template import ReportTemplate, TemplateField
from app.models.user import User


class Report(TimestampMixin, Base):
    __tablename__ = "reports"
    # created_at is indexed for date-range filters and dashboard trends.
    __table_args__ = (Index("ix_reports_created_at", "created_at"),)

    id: Mapped[BigIntPk]
    template_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("report_templates.id"), index=True)
    department_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("departments.id"))
    uploaded_by_id: Mapped[int] = mapped_column("uploaded_by", BigInteger, ForeignKey("users.id"), index=True)
    document_name: Mapped[str] = mapped_column(String(255))
    original_filename: Mapped[str] = mapped_column(String(255))
    status: Mapped[ReportStatus] = mapped_column(enum_column(ReportStatus), index=True)
    report_month: Mapped[str | None] = mapped_column(String(50))
    report_date: Mapped[date | None] = mapped_column(Date)
    average_confidence: Mapped[float | None] = mapped_column(Float)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    approved_by_id: Mapped[int | None] = mapped_column("approved_by", BigInteger, ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Many-to-one links are loaded eagerly (one extra SELECT per batch) so lists never trigger N+1 queries.
    template: Mapped[ReportTemplate] = relationship(lazy="selectin")
    department: Mapped[Department | None] = relationship(lazy="selectin")
    uploader: Mapped[User] = relationship(foreign_keys=[uploaded_by_id], lazy="selectin")
    approver: Mapped[User | None] = relationship(foreign_keys=[approved_by_id], lazy="selectin")

    files: Mapped[list["ReportFile"]] = relationship(back_populates="report", cascade="all, delete-orphan", passive_deletes=True)

    def __repr__(self) -> str:
        return f"<Report id={self.id} status={self.status}>"


class ReportFile(CreatedAtMixin, Base):
    __tablename__ = "report_files"
    __table_args__ = (UniqueConstraint("report_id", "kind"),)

    id: Mapped[BigIntPk]
    report_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("reports.id", ondelete="CASCADE"))
    kind: Mapped[ReportFileKind] = mapped_column(enum_column(ReportFileKind))
    storage_key: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    original_filename: Mapped[str] = mapped_column(String(255))

    report: Mapped[Report] = relationship(back_populates="files")


class ReportLine(CreatedAtMixin, Base):
    """One table row on the paper form. LINE-scoped field values point at it."""

    __tablename__ = "report_lines"
    __table_args__ = (UniqueConstraint("report_id", "row_index"),)

    id: Mapped[BigIntPk]
    report_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("reports.id", ondelete="CASCADE"))
    row_index: Mapped[int]


class ReportFieldValue(CreatedAtMixin, Base):
    __tablename__ = "report_field_values"

    id: Mapped[BigIntPk]
    report_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    template_field_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("template_fields.id"), index=True)
    line_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("report_lines.id", ondelete="CASCADE"), index=True)
    raw_value: Mapped[str | None] = mapped_column(Text)
    original_value: Mapped[str | None] = mapped_column(Text)  # what OCR read
    corrected_value: Mapped[str | None] = mapped_column(Text)  # what an inspector typed, if anything
    numeric_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    confidence: Mapped[float | None] = mapped_column(Float)
    status: Mapped[FieldValueStatus] = mapped_column(enum_column(FieldValueStatus))
    bbox_x: Mapped[float | None] = mapped_column(Float)
    bbox_y: Mapped[float | None] = mapped_column(Float)
    bbox_width: Mapped[float | None] = mapped_column(Float)
    bbox_height: Mapped[float | None] = mapped_column(Float)
    page_index: Mapped[int] = mapped_column(default=0, server_default="0")
    corrected_by_id: Mapped[int | None] = mapped_column("corrected_by", BigInteger, ForeignKey("users.id"))
    corrected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    template_field: Mapped[TemplateField] = relationship(lazy="selectin")
    line: Mapped[ReportLine | None] = relationship(lazy="selectin")
    corrector: Mapped[User | None] = relationship(lazy="selectin")

    @property
    def effective_value(self) -> str | None:
        """The value shown to users: the correction if one was made, otherwise the OCR value."""
        return self.corrected_value if self.corrected_value is not None else self.original_value


class OcrExtraction(CreatedAtMixin, Base):
    """Full OCR service response for one processing run, kept for debugging and audits."""

    __tablename__ = "ocr_extractions"

    id: Mapped[BigIntPk]
    report_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    engine: Mapped[str | None] = mapped_column(String(50))
    raw_response: Mapped[dict] = mapped_column(JSONB)


class ValidationHistory(CreatedAtMixin, Base):
    __tablename__ = "validation_history"

    id: Mapped[BigIntPk]
    report_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    field_value_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("report_field_values.id", ondelete="SET NULL"))
    action: Mapped[HistoryAction] = mapped_column(enum_column(HistoryAction))
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    actor_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))

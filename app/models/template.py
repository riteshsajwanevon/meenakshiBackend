from sqlalchemy import BigInteger, Float, ForeignKey, String, Text, UniqueConstraint, false, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, BigIntPk, TimestampMixin, enum_column
from app.models.enums import FieldDataType, FieldScope


class ReportTemplate(TimestampMixin, Base):
    """A paper form layout (e.g. Supplier Rejection Report) and the fields OCR should read from it."""

    __tablename__ = "report_templates"

    id: Mapped[BigIntPk]
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text)
    quantity_field_key: Mapped[str | None] = mapped_column(String(64))  # line field summed on the dashboard
    active: Mapped[bool] = mapped_column(default=True, server_default=true())

    fields: Mapped[list["TemplateField"]] = relationship(
        back_populates="template",
        lazy="selectin",
        order_by="TemplateField.column_order",
        cascade="all, delete-orphan",
    )


class TemplateField(Base):
    """One field on a template. Region values are fractions (0-1) of page width/height."""

    __tablename__ = "template_fields"
    __table_args__ = (UniqueConstraint("template_id", "field_key"),)

    id: Mapped[BigIntPk]
    template_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("report_templates.id", ondelete="CASCADE"), index=True)
    field_key: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(150))
    scope: Mapped[FieldScope] = mapped_column(enum_column(FieldScope))
    data_type: Mapped[FieldDataType] = mapped_column(enum_column(FieldDataType))
    required: Mapped[bool] = mapped_column(default=False, server_default=false())
    column_order: Mapped[int] = mapped_column(default=0, server_default="0")
    validation_rule: Mapped[str] = mapped_column(String(32), default="NONE", server_default="NONE")
    region_x: Mapped[float | None] = mapped_column(Float)
    region_y: Mapped[float | None] = mapped_column(Float)
    region_width: Mapped[float | None] = mapped_column(Float)
    region_height: Mapped[float | None] = mapped_column(Float)

    template: Mapped[ReportTemplate] = relationship(back_populates="fields")

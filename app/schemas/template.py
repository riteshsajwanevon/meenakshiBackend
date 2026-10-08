from pydantic import Field

from app.models.enums import FieldDataType, FieldScope
from app.schemas.common import ApiModel


class TemplateFieldView(ApiModel):
    id: int
    field_key: str
    label: str
    scope: FieldScope
    data_type: FieldDataType
    required: bool
    column_order: int
    validation_rule: str
    region_x: float | None
    region_y: float | None
    region_width: float | None
    region_height: float | None


class TemplateView(ApiModel):
    id: int
    code: str
    name: str
    description: str | None
    quantity_field_key: str | None
    active: bool
    fields: list[TemplateFieldView]


class TemplatePatchRequest(ApiModel):
    """All fields optional; only the ones present in the request body are changed."""

    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    active: bool | None = None

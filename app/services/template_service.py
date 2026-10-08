from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models import ReportTemplate, User
from app.models.enums import AuditAction, EntityType
from app.schemas.template import TemplatePatchRequest, TemplateView
from app.services import audit_service
from app.services.ocr_client import TemplateFieldPayload, TemplatePayload


def list_templates(db: Session, active_only: bool) -> list[TemplateView]:
    stmt = select(ReportTemplate).order_by(ReportTemplate.name)
    if active_only:
        stmt = stmt.where(ReportTemplate.active.is_(True))
    return [TemplateView.model_validate(template) for template in db.scalars(stmt)]


def get_template(db: Session, template_id: int) -> TemplateView:
    return TemplateView.model_validate(_get(db, template_id))


def update_template(db: Session, actor: User, template_id: int, request: TemplatePatchRequest) -> TemplateView:
    template = _get(db, template_id)
    provided = request.model_fields_set  # only change what the client actually sent

    changes = {}
    if "name" in provided and request.name is not None:
        template.name = request.name.strip()
        changes["name"] = template.name
    if "description" in provided:
        template.description = request.description
        changes["description"] = template.description
    if "active" in provided and request.active is not None:
        template.active = request.active
        changes["active"] = template.active

    if changes:
        audit_service.record(
            db, actor=actor, action=AuditAction.TEMPLATE_UPDATED, entity_type=EntityType.TEMPLATE, entity_id=template.id, details=changes
        )
        db.commit()
    return TemplateView.model_validate(template)


def build_ocr_payload(template: ReportTemplate) -> TemplatePayload:
    return TemplatePayload(
        code=template.code,
        quantity_field_key=template.quantity_field_key,
        fields=[
            TemplateFieldPayload(
                field_key=field.field_key,
                label=field.label,
                scope=field.scope,
                data_type=field.data_type,
                required=field.required,
                column_order=field.column_order,
                validation_rule=field.validation_rule,
                region_x=field.region_x,
                region_y=field.region_y,
                region_width=field.region_width,
                region_height=field.region_height,
            )
            for field in template.fields
        ],
    )


def _get(db: Session, template_id: int) -> ReportTemplate:
    template = db.get(ReportTemplate, template_id)
    if template is None:
        raise NotFoundError("Report template not found")
    return template

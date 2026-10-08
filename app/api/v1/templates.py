from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.schemas.template import TemplatePatchRequest, TemplateView
from app.services import template_service

router = APIRouter(prefix="/templates", tags=["Templates"])


@router.get("", response_model=list[TemplateView])
def list_templates(db: DbSession, _: CurrentUser, active_only: Annotated[bool, Query(alias="activeOnly")] = False):
    return template_service.list_templates(db, active_only)


@router.get("/{template_id}", response_model=TemplateView)
def get_template(template_id: int, db: DbSession, _: CurrentUser):
    return template_service.get_template(db, template_id)


@router.patch("/{template_id}", response_model=TemplateView)
def update_template(template_id: int, body: TemplatePatchRequest, db: DbSession, user: AdminUser):
    return template_service.update_template(db, user, template_id, body)

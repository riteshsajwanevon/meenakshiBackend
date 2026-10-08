"""Dashboard, audit logs, notifications and settings."""

from fastapi import APIRouter, Response

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.schemas.common import PageResponse
from app.schemas.misc import AuditView, DashboardSummary, NameQuantity, NotificationView, SettingView, TrendPoint
from app.services import audit_service, dashboard_service, notification_service, settings_service

dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
audit_router = APIRouter(prefix="/audit-logs", tags=["Audit"])
notifications_router = APIRouter(prefix="/notifications", tags=["Notifications"])
settings_router = APIRouter(prefix="/settings", tags=["Settings"])


@dashboard_router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(db: DbSession, _: CurrentUser):
    return dashboard_service.summary(db)


@dashboard_router.get("/rejections", response_model=list[NameQuantity])
def dashboard_rejections(db: DbSession, _: CurrentUser):
    return dashboard_service.top_rejection_reasons(db)


@dashboard_router.get("/suppliers", response_model=list[NameQuantity])
def dashboard_suppliers(db: DbSession, _: CurrentUser):
    return dashboard_service.top_suppliers(db)


@dashboard_router.get("/trends", response_model=list[TrendPoint])
def dashboard_trends(db: DbSession, _: CurrentUser, granularity: str = "daily"):
    return dashboard_service.trends(db, granularity)


@audit_router.get("", response_model=PageResponse[AuditView])
def list_audit_logs(db: DbSession, _: AdminUser, page: int = 0, size: int = 20):
    return audit_service.list_logs(db, page, size)


@notifications_router.get("", response_model=list[NotificationView])
def list_notifications(db: DbSession, user: CurrentUser):
    return notification_service.list_recent(db, user)


@notifications_router.post("/{notification_id}/read", status_code=200, response_class=Response)
def mark_notification_read(notification_id: int, db: DbSession, user: CurrentUser):
    notification_service.mark_read(db, user, notification_id)
    return Response(status_code=200)


@settings_router.get("", response_model=list[SettingView])
def list_settings(db: DbSession, _: AdminUser):
    return settings_service.list_settings(db)


@settings_router.patch("", response_model=list[SettingView])
def update_settings(body: dict[str, str | int | float | bool], db: DbSession, admin: AdminUser):
    """Body is a map of setting key -> new value. Unknown keys are ignored."""
    changes = {key: str(value).lower() if isinstance(value, bool) else str(value) for key, value in body.items()}
    return settings_service.update_settings(db, admin, changes)

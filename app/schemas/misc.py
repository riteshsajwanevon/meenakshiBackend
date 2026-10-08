"""Small response models: dashboard, audit log, notifications and settings."""

from datetime import datetime

from app.schemas.common import ApiModel


class DashboardSummary(ApiModel):
    total_reports: int
    pending_validation: int
    validated_reports: int
    approved_reports: int
    processing: int
    failed: int
    rejection_quantity: float
    rework_quantity: float
    segregation_quantity: float
    scrap_quantity: float


class NameQuantity(ApiModel):
    name: str
    quantity: float
    count: int


class TrendPoint(ApiModel):
    bucket: str  # YYYY-MM-DD: start of the day, week or month
    reports: int
    quantity: float


class AuditView(ApiModel):
    id: int
    actor: str | None
    action: str
    entity_type: str
    entity_id: str | None
    correlation_id: str | None
    created_at: datetime


class NotificationView(ApiModel):
    id: int
    title: str
    body: str
    read: bool
    created_at: datetime


class SettingView(ApiModel):
    key: str
    value: str

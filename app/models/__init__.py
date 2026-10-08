"""All ORM models. Importing this package registers every table on Base.metadata (needed by Alembic)."""

from app.models.activity import AppSetting, AuditLog, Notification
from app.models.department import Department
from app.models.report import (
    OcrExtraction,
    Report,
    ReportFieldValue,
    ReportFile,
    ReportLine,
    ValidationHistory,
)
from app.models.template import ReportTemplate, TemplateField
from app.models.user import PasswordResetToken, RefreshToken, Role, User, user_roles

__all__ = [
    "AppSetting",
    "AuditLog",
    "Department",
    "Notification",
    "OcrExtraction",
    "PasswordResetToken",
    "RefreshToken",
    "Report",
    "ReportFieldValue",
    "ReportFile",
    "ReportLine",
    "ReportTemplate",
    "Role",
    "TemplateField",
    "User",
    "ValidationHistory",
    "user_roles",
]

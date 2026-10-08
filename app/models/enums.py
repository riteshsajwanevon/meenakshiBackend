from enum import StrEnum


class RoleCode(StrEnum):
    ADMIN = "ADMIN"
    QUALITY_INSPECTOR = "QUALITY_INSPECTOR"
    OPERATOR = "OPERATOR"
    VIEWER = "VIEWER"

    @property
    def authority(self) -> str:
        """Spring-style authority name used in JWT `roles` claims, e.g. ROLE_ADMIN."""
        return f"ROLE_{self.value}"


class ReportStatus(StrEnum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    OCR_COMPLETED = "OCR_COMPLETED"
    VALIDATION_REQUIRED = "VALIDATION_REQUIRED"
    VALIDATED = "VALIDATED"
    APPROVED = "APPROVED"
    FAILED = "FAILED"


class FieldScope(StrEnum):
    HEADER = "HEADER"
    LINE = "LINE"
    FOOTER = "FOOTER"


class FieldDataType(StrEnum):
    TEXT = "TEXT"
    NUMBER = "NUMBER"
    DATE = "DATE"
    MONTH = "MONTH"


class FieldValueStatus(StrEnum):
    VERIFIED = "VERIFIED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    ERROR = "ERROR"
    EMPTY = "EMPTY"


class ReportFileKind(StrEnum):
    ORIGINAL = "ORIGINAL"
    PREVIEW = "PREVIEW"


class HistoryAction(StrEnum):
    CORRECTED = "CORRECTED"
    VALIDATED = "VALIDATED"
    APPROVED = "APPROVED"


class AuditAction(StrEnum):
    REPORT_UPLOADED = "REPORT_UPLOADED"
    REPORT_PROCESSED = "REPORT_PROCESSED"
    REPORT_PROCESSING_FAILED = "REPORT_PROCESSING_FAILED"
    REPORT_VALIDATED = "REPORT_VALIDATED"
    REPORT_APPROVED = "REPORT_APPROVED"
    USER_CREATED = "USER_CREATED"
    USER_REGISTERED = "USER_REGISTERED"
    USER_UPDATED = "USER_UPDATED"
    PASSWORD_RESET = "PASSWORD_RESET"
    TEMPLATE_UPDATED = "TEMPLATE_UPDATED"
    SETTINGS_UPDATED = "SETTINGS_UPDATED"


class EntityType(StrEnum):
    USER = "USER"
    REPORT = "REPORT"
    TEMPLATE = "TEMPLATE"
    SETTINGS = "SETTINGS"

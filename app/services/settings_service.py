"""Admin-editable key/value settings stored in app_settings."""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError
from app.models import AppSetting, User
from app.models.enums import AuditAction, EntityType
from app.schemas.misc import SettingView
from app.services import audit_service

logger = logging.getLogger(__name__)

VERIFIED_THRESHOLD_KEY = "ocr.verified-threshold"
REVIEW_THRESHOLD_KEY = "ocr.review-threshold"
DEFAULT_VERIFIED_THRESHOLD = 0.85
DEFAULT_REVIEW_THRESHOLD = 0.60

# Settings that must be numbers, with their allowed (min, max) range; None means unbounded.
NUMERIC_SETTINGS: dict[str, tuple[float, float | None]] = {
    VERIFIED_THRESHOLD_KEY: (0.0, 1.0),
    REVIEW_THRESHOLD_KEY: (0.0, 1.0),
    "upload.max-bytes": (1, None),
}


def list_settings(db: Session) -> list[SettingView]:
    return [SettingView(key=s.key, value=s.value) for s in db.scalars(select(AppSetting).order_by(AppSetting.key))]


def update_settings(db: Session, actor: User, changes: dict[str, str]) -> list[SettingView]:
    """Update existing keys only; unknown keys are ignored (as in the Java backend)."""
    existing = {s.key: s for s in db.scalars(select(AppSetting).where(AppSetting.key.in_(changes)))}
    changed: dict[str, str] = {}
    for key, value in changes.items():
        setting = existing.get(key)
        if setting is None:
            logger.info("Ignoring unknown setting %r", key)
            continue
        _check_value(key, value)
        if setting.value != value:
            setting.value = value
            changed[key] = value

    if changed:
        audit_service.record(db, actor=actor, action=AuditAction.SETTINGS_UPDATED, entity_type=EntityType.SETTINGS, details=changed)
        db.commit()
    return list_settings(db)


def ocr_thresholds(db: Session) -> tuple[float, float]:
    """(verified, review) confidence thresholds used to set field status after OCR."""
    values = dict(
        db.execute(
            select(AppSetting.key, AppSetting.value).where(AppSetting.key.in_([VERIFIED_THRESHOLD_KEY, REVIEW_THRESHOLD_KEY]))
        ).all()
    )
    return (
        _to_float(values.get(VERIFIED_THRESHOLD_KEY), DEFAULT_VERIFIED_THRESHOLD),
        _to_float(values.get(REVIEW_THRESHOLD_KEY), DEFAULT_REVIEW_THRESHOLD),
    )


def _check_value(key: str, value: str) -> None:
    if key not in NUMERIC_SETTINGS:
        return
    minimum, maximum = NUMERIC_SETTINGS[key]
    number = _to_float(value, None)
    if number is None or number < minimum or (maximum is not None and number > maximum):
        allowed = f"between {minimum} and {maximum}" if maximum is not None else f"at least {minimum}"
        raise BadRequestError(f"Setting '{key}' must be a number {allowed}")


def _to_float(value: str | None, default: float | None) -> float | None:
    try:
        return float(value) if value is not None else default
    except ValueError:
        logger.warning("Setting value %r is not a number; using default %s", value, default)
        return default

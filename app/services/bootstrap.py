"""Creates the first admin / inspector / operator accounts on a fresh database."""

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models import Role, User
from app.models.enums import RoleCode

logger = logging.getLogger(__name__)

DEFAULT_PASSWORD = "ChangeMe123!"


def seed_initial_users(db: Session) -> None:
    """Runs on startup. Does nothing once any user exists."""
    if db.scalar(select(func.count(User.id))):
        return

    roles = {role.code: role for role in db.scalars(select(Role))}
    if len(roles) < len(RoleCode):
        raise RuntimeError("Roles are missing from the database. Run `alembic upgrade head` first.")

    accounts = [
        (settings.INITIAL_ADMIN_EMAIL, settings.INITIAL_ADMIN_PASSWORD, settings.INITIAL_ADMIN_NAME, RoleCode.ADMIN),
        (settings.INITIAL_INSPECTOR_EMAIL, settings.INITIAL_INSPECTOR_PASSWORD, settings.INITIAL_INSPECTOR_NAME, RoleCode.QUALITY_INSPECTOR),
        (settings.INITIAL_OPERATOR_EMAIL, settings.INITIAL_OPERATOR_PASSWORD, settings.INITIAL_OPERATOR_NAME, RoleCode.OPERATOR),
    ]
    created = []
    for email, password, name, role in accounts:
        if not email or not password:
            continue
        db.add(User(email=email.strip().lower(), full_name=name, password_hash=hash_password(password), roles=[roles[role]]))
        created.append(f"{email} ({role})")
        if password == DEFAULT_PASSWORD:
            logger.warning("Initial user %s uses the default password. Change it after first login.", email)
    db.commit()
    if created:
        logger.info("Created initial users: %s", ", ".join(created))

"""Self-registration, login, refresh-token rotation, logout and password reset."""

import logging
from datetime import timedelta
from functools import lru_cache

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.core.errors import BadRequestError, ConflictError, UnauthorizedError
from app.core.time import utcnow
from app.models import PasswordResetToken, RefreshToken, Role, User
from app.models.enums import AuditAction, EntityType
from app.schemas.auth import AuthResponse, RegisterRequest, UserResponse
from app.services import audit_service, email_service

logger = logging.getLogger(__name__)

INVALID_CREDENTIALS = "The email or password is incorrect"
ACCOUNT_DISABLED = "Your account has been deactivated. Please contact an administrator."
SESSION_EXPIRED = "Your session has expired. Please sign in again."
INVALID_RESET_TOKEN = "This password reset link is invalid or has expired."


def find_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.strip().lower()))


def register(db: Session, request: RegisterRequest) -> UserResponse:
    """Self sign-up. The account is active at once; its role comes from settings, never from the request."""
    email = request.email.strip().lower()
    if find_user_by_email(db, email) is not None:
        raise ConflictError("A user with this email already exists")

    role = db.scalar(select(Role).where(Role.code == settings.SELF_REGISTRATION_ROLE))
    if role is None:
        raise RuntimeError(f"Role {settings.SELF_REGISTRATION_ROLE} is missing. Run `alembic upgrade head`.")

    user = User(
        email=email,
        full_name=request.full_name.strip(),
        password_hash=security.hash_password(request.password),
        roles=[role],
    )
    db.add(user)
    db.flush()  # assigns user.id for the audit entry
    audit_service.record(
        db, actor=user, action=AuditAction.USER_REGISTERED, entity_type=EntityType.USER, entity_id=user.id,
        details={"email": email, "role": role.code},
    )
    db.commit()
    logger.info("User %s registered with role %s", user.id, role.code)
    return UserResponse.from_model(user)


def login(db: Session, email: str, password: str) -> AuthResponse:
    user = find_user_by_email(db, email)
    if user is None:
        security.verify_password(password, _dummy_password_hash())  # same timing whether or not the account exists
        logger.info("Login failed: no account for %s", email)
        raise UnauthorizedError(INVALID_CREDENTIALS)
    if not security.verify_password(password, user.password_hash):
        logger.info("Login failed: wrong password for user %s", user.id)
        raise UnauthorizedError(INVALID_CREDENTIALS)
    if not user.active:
        raise UnauthorizedError(ACCOUNT_DISABLED)

    response = _issue_tokens(db, user)
    db.commit()
    logger.info("User %s logged in", user.id)
    return response


def refresh(db: Session, raw_refresh_token: str) -> AuthResponse:
    """Exchange a refresh token for a new token pair. The old refresh token is revoked (rotation)."""
    if security.decode_token(raw_refresh_token, security.REFRESH_TOKEN_TYPE) is None:
        raise UnauthorizedError(SESSION_EXPIRED)

    stored = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == security.sha256_hex(raw_refresh_token)).with_for_update()
    )
    if stored is None or stored.revoked_at is not None or stored.expires_at <= utcnow():
        raise UnauthorizedError(SESSION_EXPIRED)

    user = db.get(User, stored.user_id)
    if user is None or not user.active:
        raise UnauthorizedError(SESSION_EXPIRED)

    stored.revoked_at = utcnow()
    response = _issue_tokens(db, user)
    db.commit()
    return response


def logout(db: Session, raw_refresh_token: str | None) -> None:
    if not raw_refresh_token:
        return
    stored = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == security.sha256_hex(raw_refresh_token)))
    if stored is not None and stored.revoked_at is None:
        stored.revoked_at = utcnow()
        db.commit()


def forgot_password(db: Session, email: str) -> None:
    """Issue a reset token if the account exists. Callers always get the same answer either way."""
    user = find_user_by_email(db, email)
    if user is None or not user.active:
        logger.info("Password reset requested for unknown or inactive account")
        return

    token = security.generate_reset_token()
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=security.sha256_hex(token),
            expires_at=utcnow() + timedelta(minutes=settings.PASSWORD_RESET_MINUTES),
        )
    )
    db.commit()
    email_service.send_password_reset(user.email, user.full_name, token)


def reset_password(db: Session, raw_token: str, new_password: str) -> None:
    stored = db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == security.sha256_hex(raw_token)).with_for_update()
    )
    if stored is None or stored.used_at is not None or stored.expires_at <= utcnow():
        raise BadRequestError(INVALID_RESET_TOKEN)
    user = db.get(User, stored.user_id)
    if user is None or not user.active:
        raise BadRequestError(INVALID_RESET_TOKEN)

    now = utcnow()
    user.password_hash = security.hash_password(new_password)
    stored.used_at = now
    # Sign the user out everywhere: existing refresh tokens stop working.
    db.execute(
        update(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)).values(revoked_at=now)
    )
    audit_service.record(db, actor=user, action=AuditAction.PASSWORD_RESET, entity_type=EntityType.USER, entity_id=user.id)
    db.commit()
    logger.info("Password reset for user %s", user.id)


def revoke_all_refresh_tokens(db: Session, user_id: int) -> None:
    """Adds the revocation to the current transaction (caller commits)."""
    db.execute(
        update(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)).values(revoked_at=utcnow())
    )


def _issue_tokens(db: Session, user: User) -> AuthResponse:
    access = security.create_access_token(
        user_id=user.id, email=user.email, roles=[code.authority for code in user.role_codes]
    )
    refresh_token = security.create_refresh_token(user_id=user.id, email=user.email)
    db.add(
        RefreshToken(user_id=user.id, token_hash=security.sha256_hex(refresh_token.token), expires_at=refresh_token.expires_at)
    )
    user.last_active_at = utcnow()
    return AuthResponse(
        access_token=access.token,
        refresh_token=refresh_token.token,
        expires_in=settings.JWT_ACCESS_MINUTES * 60,
        user=UserResponse.from_model(user),
    )


@lru_cache
def _dummy_password_hash() -> str:
    return security.hash_password("timing-equaliser")

"""Password hashing, JWT access/refresh tokens and token helpers."""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

import bcrypt
import jwt

from app.core.config import settings
from app.core.time import utcnow

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"
JWT_ALGORITHM = "HS256"

# bcrypt only looks at the first 72 bytes. Truncating explicitly keeps hashing and
# verification consistent (newer bcrypt versions raise instead of truncating).
_BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    """Also accepts `$2a$` hashes created by Spring's BCryptPasswordEncoder."""
    try:
        return bcrypt.checkpw(_password_bytes(password), password_hash.encode("ascii"))
    except ValueError:  # malformed hash stored in the database
        return False


def _password_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


@dataclass(frozen=True)
class IssuedToken:
    token: str
    expires_at: datetime


def create_access_token(*, user_id: int, email: str, roles: list[str]) -> IssuedToken:
    expires_at = utcnow() + timedelta(minutes=settings.JWT_ACCESS_MINUTES)
    claims = {"sub": email, "uid": user_id, "roles": roles, "typ": ACCESS_TOKEN_TYPE}
    return IssuedToken(_encode(claims, settings.JWT_SECRET, expires_at), expires_at)


def create_refresh_token(*, user_id: int, email: str) -> IssuedToken:
    expires_at = utcnow() + timedelta(days=settings.JWT_REFRESH_DAYS)
    claims = {"sub": email, "uid": user_id, "typ": REFRESH_TOKEN_TYPE}
    return IssuedToken(_encode(claims, settings.JWT_REFRESH_SECRET, expires_at), expires_at)


def decode_token(token: str, expected_type: str) -> dict | None:
    """Return the token's claims, or None if it is malformed, expired, wrongly signed or of the wrong type."""
    secret = settings.JWT_SECRET if expected_type == ACCESS_TOKEN_TYPE else settings.JWT_REFRESH_SECRET
    try:
        claims = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM], options={"require": ["exp", "sub", "uid", "typ"]})
    except jwt.PyJWTError:
        return None
    if claims.get("typ") != expected_type:
        return None
    return claims


def _encode(claims: dict, secret: str, expires_at: datetime) -> str:
    # jti makes every token unique, so two tokens issued in the same second never share a stored hash.
    payload = {**claims, "iat": utcnow(), "exp": expires_at, "jti": uuid.uuid4().hex}
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def sha256_hex(value: str) -> str:
    """Refresh and password-reset tokens are stored as SHA-256 hex, never in plain text."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def generate_reset_token() -> str:
    return secrets.token_hex(32)


def generate_temporary_password() -> str:
    """One-time password for admin-created users, e.g. 'Mp1a2b3c4d5e6f7'."""
    return "Mp" + secrets.token_hex(7)[:13]

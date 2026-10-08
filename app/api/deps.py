"""Shared FastAPI dependencies: database session, current user and role checks."""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core import security
from app.core.errors import ForbiddenError, UnauthorizedError
from app.db.session import get_db
from app.models import User
from app.models.enums import RoleCode

# auto_error=False: we raise our own 401 in the standard error format (FastAPI's default is a bare 403).
bearer_scheme = HTTPBearer(auto_error=False, description="Paste the accessToken returned by POST /api/v1/auth/login")

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None:
        raise UnauthorizedError("Authentication is required")
    claims = security.decode_token(credentials.credentials, security.ACCESS_TOKEN_TYPE)
    if claims is None:
        raise UnauthorizedError("Your session has expired. Please sign in again.")
    user = db.get(User, claims["uid"])
    if user is None or not user.active:
        raise UnauthorizedError("Your account is not active")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*allowed: RoleCode):
    def check_role(user: CurrentUser) -> User:
        if not user.has_any_role(*allowed):
            raise ForbiddenError("You do not have permission to perform this action")
        return user

    return check_role


AdminUser = Annotated[User, Depends(require_roles(RoleCode.ADMIN))]
UploaderUser = Annotated[User, Depends(require_roles(RoleCode.ADMIN, RoleCode.QUALITY_INSPECTOR, RoleCode.OPERATOR))]
ReviewerUser = Annotated[User, Depends(require_roles(RoleCode.ADMIN, RoleCode.QUALITY_INSPECTOR))]

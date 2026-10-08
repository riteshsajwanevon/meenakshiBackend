from fastapi import APIRouter, Response

from app.api.deps import CurrentUser, DbSession
from app.schemas.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    UserResponse,
)
from app.schemas.common import MessageResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])

FORGOT_PASSWORD_MESSAGE = "If an account exists for that email, a reset token has been issued."
RESET_PASSWORD_MESSAGE = "Your password has been updated."


@router.post("/register", response_model=UserResponse, status_code=201)
def register(body: RegisterRequest, db: DbSession):
    """Self sign-up. The new user can log in straight away, with the SELF_REGISTRATION_ROLE role (default VIEWER)."""
    return auth_service.register(db, body)


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest, db: DbSession):
    return auth_service.login(db, body.email, body.password)


@router.post("/refresh", response_model=AuthResponse)
def refresh(body: RefreshRequest, db: DbSession):
    return auth_service.refresh(db, body.refresh_token)


@router.post("/logout", status_code=200, response_class=Response)
def logout(db: DbSession, body: LogoutRequest | None = None):
    """Works with or without an access token; revokes the refresh token if one is sent."""
    auth_service.logout(db, body.refresh_token if body else None)
    return Response(status_code=200)


@router.get("/profile", response_model=UserResponse)
@router.get("/me", response_model=UserResponse, deprecated=True)  # old path used by the existing frontend
def profile(user: CurrentUser):
    """The signed-in user's own profile."""
    return UserResponse.from_model(user)


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(body: ForgotPasswordRequest, db: DbSession):
    auth_service.forgot_password(db, body.email)
    return MessageResponse(message=FORGOT_PASSWORD_MESSAGE)


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(body: ResetPasswordRequest, db: DbSession):
    auth_service.reset_password(db, body.token, body.password)
    return MessageResponse(message=RESET_PASSWORD_MESSAGE)

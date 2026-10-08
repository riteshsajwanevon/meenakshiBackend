from pydantic import EmailStr, Field

from app.models import User
from app.models.enums import RoleCode
from app.schemas.common import ApiModel

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 72  # bcrypt limit


class RegisterRequest(ApiModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)


class LoginRequest(ApiModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class RefreshRequest(ApiModel):
    refresh_token: str = Field(min_length=1)


class LogoutRequest(ApiModel):
    refresh_token: str | None = None


class ForgotPasswordRequest(ApiModel):
    email: EmailStr


class ResetPasswordRequest(ApiModel):
    token: str = Field(min_length=1)
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)


class UserResponse(ApiModel):
    id: int
    email: str
    full_name: str
    roles: list[RoleCode]
    active: bool

    @classmethod
    def from_model(cls, user: User) -> "UserResponse":
        return cls(id=user.id, email=user.email, full_name=user.full_name, roles=user.role_codes, active=user.active)


class AuthResponse(ApiModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int  # seconds until the access token expires
    user: UserResponse

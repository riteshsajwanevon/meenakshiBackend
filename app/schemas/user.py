from datetime import datetime

from pydantic import EmailStr, Field

from app.models import User
from app.models.enums import RoleCode
from app.schemas.common import ApiModel


class UserView(ApiModel):
    id: int
    email: str
    full_name: str
    roles: list[RoleCode]
    reports_submitted: int
    last_active_at: datetime | None
    active: bool

    @classmethod
    def from_model(cls, user: User, reports_submitted: int) -> "UserView":
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            roles=user.role_codes,
            reports_submitted=reports_submitted,
            last_active_at=user.last_active_at,
            active=user.active,
        )


class UserStats(ApiModel):
    total_users: int
    active_now: int
    active_accounts: int
    reports_today: int


class CreateUserRequest(ApiModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=150)
    role: RoleCode


class CreateUserResponse(ApiModel):
    user: UserView
    temporary_password: str


class UpdateUserRequest(ApiModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    role: RoleCode | None = None
    active: bool | None = None


class DepartmentView(ApiModel):
    id: int
    code: str
    name: str

from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, Table, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, BigIntPk, CreatedAtMixin, TimestampMixin, enum_column
from app.models.enums import RoleCode

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", BigInteger, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[BigIntPk]
    code: Mapped[RoleCode] = mapped_column(enum_column(RoleCode), unique=True)
    name: Mapped[str] = mapped_column(String(100))


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[BigIntPk]
    email: Mapped[str] = mapped_column(String(255), unique=True)  # always stored lower-case
    full_name: Mapped[str] = mapped_column(String(150))
    password_hash: Mapped[str] = mapped_column(String(100))
    active: Mapped[bool] = mapped_column(default=True, server_default=true())
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    roles: Mapped[list[Role]] = relationship(secondary=user_roles, lazy="selectin", order_by=Role.id)

    @property
    def role_codes(self) -> list[RoleCode]:
        return [role.code for role in self.roles]

    def has_any_role(self, *codes: RoleCode) -> bool:
        return any(code in codes for code in self.role_codes)

    @property
    def is_operator_only(self) -> bool:
        return set(self.role_codes) == {RoleCode.OPERATOR}

    @property
    def is_viewer_only(self) -> bool:
        return set(self.role_codes) == {RoleCode.VIEWER}

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"


class RefreshToken(CreatedAtMixin, Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[BigIntPk]
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PasswordResetToken(CreatedAtMixin, Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[BigIntPk]
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

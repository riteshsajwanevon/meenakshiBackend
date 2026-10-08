from sqlalchemy import String, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BigIntPk, CreatedAtMixin


class Department(CreatedAtMixin, Base):
    __tablename__ = "departments"

    id: Mapped[BigIntPk]
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(150))
    active: Mapped[bool] = mapped_column(default=True, server_default=true())

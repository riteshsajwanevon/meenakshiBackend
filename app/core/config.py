"""Application settings.

Values are read from environment variables first, then from the `.env` file.
Variable names mirror the Java backend so the same deployment config works for both.
"""

from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url

from app.models.enums import RoleCode

MIN_JWT_SECRET_BYTES = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Application ---
    APP_NAME: str = "Meenakshi Quality Backend"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = False  # one JSON object per log line; enable in production log pipelines

    # --- Database ---
    # Accepts SQLAlchemy URLs (postgresql+psycopg://...) and Java-style JDBC URLs (jdbc:postgresql://...).
    # DATABASE_USERNAME / DATABASE_PASSWORD, when set, override credentials inside the URL.
    DATABASE_URL: str = "postgresql+psycopg://localhost:5432/meenakshi"
    DATABASE_USERNAME: str | None = None
    DATABASE_PASSWORD: str | None = None
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # --- Auth ---
    JWT_SECRET: str
    JWT_REFRESH_SECRET: str
    JWT_ACCESS_MINUTES: int = 30
    JWT_REFRESH_DAYS: int = 7
    PASSWORD_RESET_MINUTES: int = 60

    # Role given to people who sign up through POST /auth/register (the request cannot choose one).
    SELF_REGISTRATION_ROLE: RoleCode = RoleCode.VIEWER

    # --- HTTP ---
    CORS_ORIGINS: str = "http://localhost:8081,http://localhost:19006,http://localhost:3000,http://localhost:5173"

    # --- Files & OCR ---
    FILE_STORAGE_PATH: Path = Path("./data/files")
    MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024
    OCR_SERVICE_URL: str = "http://localhost:8090"
    OCR_TIMEOUT_SECONDS: float = 120

    # --- Email (optional: when SMTP_HOST is empty, password reset tokens are written to the log) ---
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_STARTTLS: bool = True
    SMTP_FROM: str = "no-reply@meenakshi.in"
    PASSWORD_RESET_URL: str | None = None  # frontend page; the token is appended as ?token=...

    # --- Bootstrap users (created only when the users table is empty) ---
    INITIAL_ADMIN_EMAIL: str | None = "admin@meenakshi.in"
    INITIAL_ADMIN_PASSWORD: str | None = "ChangeMe123!"
    INITIAL_ADMIN_NAME: str = "Meenakshi Admin"
    INITIAL_INSPECTOR_EMAIL: str | None = "inspector@meenakshi.in"
    INITIAL_INSPECTOR_PASSWORD: str | None = "ChangeMe123!"
    INITIAL_INSPECTOR_NAME: str = "Quality Inspector"
    INITIAL_OPERATOR_EMAIL: str | None = "operator@meenakshi.in"
    INITIAL_OPERATOR_PASSWORD: str | None = "ChangeMe123!"
    INITIAL_OPERATOR_NAME: str = "Line Operator"

    @field_validator("JWT_SECRET", "JWT_REFRESH_SECRET")
    @classmethod
    def _secret_is_long_enough(cls, value: str) -> str:
        if len(value.encode("utf-8")) < MIN_JWT_SECRET_BYTES:
            raise ValueError(f"must be at least {MIN_JWT_SECRET_BYTES} bytes long")
        return value

    @model_validator(mode="after")
    def _secrets_are_different(self) -> "Settings":
        if self.JWT_SECRET == self.JWT_REFRESH_SECRET:
            raise ValueError("JWT_REFRESH_SECRET must be different from JWT_SECRET")
        return self

    @property
    def database_url(self) -> URL:
        url = make_url(self.DATABASE_URL.removeprefix("jdbc:"))
        if url.drivername in ("postgresql", "postgres"):
            url = url.set(drivername="postgresql+psycopg")
        if self.DATABASE_USERNAME:
            url = url.set(username=self.DATABASE_USERNAME)
        if self.DATABASE_PASSWORD:
            url = url.set(password=self.DATABASE_PASSWORD)
        return url

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()

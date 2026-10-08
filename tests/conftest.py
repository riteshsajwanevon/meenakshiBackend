"""Test setup.

Tests run against a real PostgreSQL database named "<your database>_test" on the server from
.env. It is created and migrated (alembic upgrade head) at the start of the run and dropped at the end.
The OCR service is never called: tests replace `ocr_client.extract` with a fake.
"""

import io
import os
import tempfile
from pathlib import Path

import psycopg
import pytest
from dotenv import dotenv_values
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]

# ---- Environment must be prepared before the app is imported (settings are read at import time). ----
_env = {**dotenv_values(ROOT / ".env"), **os.environ}
_base_url = make_url(_env["DATABASE_URL"].removeprefix("jdbc:"))
TEST_DATABASE = f"{_base_url.database}_test"
os.environ.update(
    {
        "DATABASE_URL": _base_url.set(database=TEST_DATABASE).render_as_string(hide_password=False),
        "JWT_SECRET": "test-access-secret-0123456789-0123456789",
        "JWT_REFRESH_SECRET": "test-refresh-secret-0123456789-0123456789",
        "FILE_STORAGE_PATH": tempfile.mkdtemp(prefix="meenakshi-test-files-"),
        "OCR_SERVICE_URL": "http://ocr.invalid",
        "SMTP_HOST": "",
        "LOG_LEVEL": "WARNING",
        "INITIAL_ADMIN_EMAIL": "admin@example.com",
        "INITIAL_ADMIN_PASSWORD": "AdminPass123",
        "INITIAL_INSPECTOR_EMAIL": "inspector@example.com",
        "INITIAL_INSPECTOR_PASSWORD": "InspectPass123",
        "INITIAL_OPERATOR_EMAIL": "operator@example.com",
        "INITIAL_OPERATOR_PASSWORD": "OperatorPass123",
    }
)

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services import ocr_client  # noqa: E402
from app.services.bootstrap import seed_initial_users  # noqa: E402
from app.services.ocr_client import OcrResponse, OcrResult  # noqa: E402

ADMIN = ("admin@example.com", "AdminPass123")
INSPECTOR = ("inspector@example.com", "InspectPass123")
OPERATOR = ("operator@example.com", "OperatorPass123")

# Tables holding data created by tests. Reference data from the seed migration is left alone.
_TEST_DATA_TABLES = "users, reports, audit_logs, notifications, refresh_tokens, password_reset_tokens"


def _admin_connection():
    url = settings.database_url
    return psycopg.connect(
        host=url.host, port=url.port or 5432, user=url.username, password=url.password, dbname="postgres", autocommit=True
    )


@pytest.fixture(scope="session", autouse=True)
def test_database():
    with _admin_connection() as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DATABASE}" WITH (FORCE)')
        conn.execute(f'CREATE DATABASE "{TEST_DATABASE}"')

    alembic_config = Config()  # no alembic.ini needed: point straight at the migrations folder
    alembic_config.set_main_option("script_location", str(ROOT / "alembic"))
    command.upgrade(alembic_config, "head")
    yield
    engine.dispose()
    with _admin_connection() as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DATABASE}" WITH (FORCE)')


@pytest.fixture(autouse=True)
def clean_data(test_database):
    """Every test starts with only reference data plus the three bootstrap users."""
    with SessionLocal() as db:
        db.execute(text(f"TRUNCATE {_TEST_DATA_TABLES} RESTART IDENTITY CASCADE"))
        db.commit()
        seed_initial_users(db)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient, credentials: tuple[str, str]) -> dict:
    response = client.post("/api/v1/auth/login", json={"email": credentials[0], "password": credentials[1]})
    assert response.status_code == 200, response.text
    return response.json()


def auth_headers(client: TestClient, credentials: tuple[str, str]) -> dict:
    return {"Authorization": f"Bearer {login(client, credentials)['accessToken']}"}


@pytest.fixture
def admin_headers(client):
    return auth_headers(client, ADMIN)


@pytest.fixture
def inspector_headers(client):
    return auth_headers(client, INSPECTOR)


@pytest.fixture
def operator_headers(client):
    return auth_headers(client, OPERATOR)


def png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (120, 80), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def template_id(client: TestClient, headers: dict, code: str) -> int:
    templates = client.get("/api/v1/templates", headers=headers).json()
    return next(t["id"] for t in templates if t["code"] == code)


def upload_png(client: TestClient, headers: dict, code: str = "SUPPLIER_REJECTION", name: str = "scan.png") -> dict:
    response = client.post(
        "/api/v1/reports",
        headers=headers,
        data={"templateId": str(template_id(client, headers, code))},
        files={"file": (name, png_bytes(), "image/png")},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _ocr_field(name, value, confidence, row=None, scope="LINE"):
    return {
        "fieldName": name, "value": value, "rawValue": value, "confidence": confidence, "scope": scope,
        "rowIndex": row, "boundingBox": {"x": 0.1, "y": 0.2, "width": 0.1, "height": 0.03}, "pageIndex": 0,
    }


SUPPLIER_REJECTION_OCR = {
    "reportType": "SUPPLIER_REJECTION",
    "documentId": "doc-1",
    "engine": "paddleocr",
    "pageCount": 1,
    "fields": [
        _ocr_field("month", "June-26", 0.95, scope="HEADER"),
        # Row 0: everything readable
        _ocr_field("date", "02/06/26", 0.95, 0),
        _ocr_field("partName", "Pipe 12.70", 0.91, 0),
        _ocr_field("supplierName", "UTTAM", 0.90, 0),
        _ocr_field("lotQty", "2,700", 0.90, 0),
        _ocr_field("rejectionQty", "250", 0.70, 0),  # NEEDS_REVIEW
        _ocr_field("okQty", "2450", 0.95, 0),
        _ocr_field("problemDescription", "Rusty", 0.50, 0),  # low confidence -> ERROR
        _ocr_field("remarks", None, None, 0),  # optional & empty -> EMPTY
        # Row 1: rejection quantity unreadable
        _ocr_field("date", "03/06/26", 0.95, 1),
        _ocr_field("partName", "MIG Wire 1.0", 0.92, 1),
        _ocr_field("supplierName", "MW Wire Tech", 0.93, 1),
        _ocr_field("lotQty", "4000", 0.90, 1),
        _ocr_field("rejectionQty", "abc", 0.90, 1),  # not a number -> ERROR
        _ocr_field("problemDescription", "rusty", 0.90, 1),
        _ocr_field("unknownColumn", "x", 0.99, 1),  # not in the template -> ignored
    ],
}


@pytest.fixture
def fake_ocr(monkeypatch):
    """Replaces the OCR HTTP call. Set `fake_ocr.response` or `fake_ocr.error` per test."""

    class FakeOcr:
        response = SUPPLIER_REJECTION_OCR
        error: Exception | None = None
        calls: list[dict] = []

        def __call__(self, **kwargs):
            self.calls.append(kwargs)
            if self.error:
                raise self.error
            return OcrResponse(result=OcrResult.model_validate(self.response), raw=self.response)

    fake = FakeOcr()
    fake.calls = []
    monkeypatch.setattr(ocr_client, "extract", fake)
    return fake

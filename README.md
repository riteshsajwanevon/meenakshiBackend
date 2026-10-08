# Meenakshi Quality Backend (Python)

FastAPI + PostgreSQL re-implementation of the Java/Spring Boot backend described in
[JAVA_BACKEND_API_AND_ARCHITECTURE_SPEC.md](JAVA_BACKEND_API_AND_ARCHITECTURE_SPEC.md).
The API is a drop-in replacement for the existing frontend: same paths (`/api/v1`), camelCase JSON,
status values, error format and multipart field names. OCR stays in the separate OCR service.

## Quick start (local)

```powershell
py -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env          # then set DATABASE_URL and the two JWT secrets
alembic upgrade head            # creates tables + seeds roles, departments, settings, templates
uvicorn app.main:app --reload --port 8080
```

* Swagger UI: http://localhost:8080/api/v1/docs/swagger (OpenAPI JSON at `/api/v1/docs`)
* Health: http://localhost:8080/actuator/health
* First start creates three users (from `INITIAL_*` settings): `admin@meenakshi.in`,
  `inspector@meenakshi.in`, `operator@meenakshi.in`, password `ChangeMe123!`. **Change them.**

With Docker instead: `JWT_SECRET=... JWT_REFRESH_SECRET=... docker compose up --build`.

## Tests

```powershell
pytest
```

Tests use a real PostgreSQL database named `<your db>_test` on the server from `.env`; it is created,
migrated and dropped automatically. The OCR service is faked, so it does not need to be running.

## Project layout

```
app/
  main.py               app factory: middleware, error handlers, routers, startup checks
  core/
    config.py           all settings (env vars / .env), names match the Java backend
    errors.py           ApiError classes + the standard JSON error body
    middleware.py       correlation id, access log, last-resort 500 handler
    logging.py          log format (text or JSON), every line carries the correlation id
    security.py         bcrypt, JWT access/refresh tokens, SHA-256 token hashing
  db/                   engine/session, declarative Base, paging helpers
  models/               SQLAlchemy tables (users, templates, reports, audit, ...)
  schemas/              request/response models (camelCase JSON)
  api/
    deps.py             DB session, current user, role checks (AdminUser, ReviewerUser, ...)
    v1/                 thin routers: parse input -> call a service -> return a schema
    health.py           /actuator/health, /actuator/info
  services/             all business logic
    report_service.py   upload -> process (OCR) -> correct -> validate -> approve
    report_status.py    the report status state machine
    field_validator.py  NUMBER / DATE / MONTH checks
    ocr_client.py       HTTP client for the OCR service (+ payload/response models)
    ...                 auth, users, templates, dashboard, export, audit, notifications, settings
  storage/              local file storage + PNG preview rendering
alembic/versions/       0001 schema, 0002 seed data (roles, departments, settings, 5 templates)
tests/                  end-to-end API tests
```

**Request flow:** router → service → models. Routers never touch the database directly; services
raise `NotFoundError`, `ConflictError`, … and never build HTTP responses.

## Debugging tips

* Every response has an `X-Correlation-Id` header (also in error bodies and audit logs). Search the
  logs for it to see everything that happened during that request. Clients may send their own.
* Set `LOG_LEVEL=DEBUG` for more detail, `LOG_JSON=true` for log aggregators.
* A report that failed OCR keeps the technical reason in `failureReason`; the full OCR response of
  every run is available from `GET /api/v1/reports/{id}/extractions`.
* Startup fails fast with a clear log line if the database is unreachable or not migrated.

## Database changes

Change the models, then generate and review a migration:

```powershell
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

## Notes and known differences from the Java backend

* **Template regions** in `0002` are evenly spaced placeholders. Port the calibrated values from
  `V3__calibrate_regions.sql` as a new migration before relying on OCR accuracy.
* **Template field keys** come from `ProjectCode/templates.json` (camelCase). If the Java seed used
  different keys, align them in a migration, since the OCR service matches on `fieldName`.
* OCR status thresholds are read from the `ocr.verified-threshold` / `ocr.review-threshold` settings
  (defaults 0.85 / 0.60) instead of being hard-coded.
* Admins cannot deactivate themselves or remove their own admin role (prevents lock-out).
* PDF exports use built-in fonts, so non-Latin characters show as `?` (XLSX/CSV are full Unicode).

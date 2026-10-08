import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.api import health
from app.api.v1 import api_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.core.request_context import CORRELATION_ID_HEADER
from app.db.session import SessionLocal
from app.services.bootstrap import seed_initial_users
from app.services.master_data_service import load_master_documents
from app.storage.local import get_storage

configure_logging(settings.LOG_LEVEL, settings.LOG_JSON)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s %s (%s)", settings.APP_NAME, settings.APP_VERSION, settings.ENVIRONMENT)
    get_storage().ensure_root()
    load_master_documents()  # fail fast if app/data/master_documents.json is malformed
    _check_database_and_seed_users()
    yield
    logger.info("Shutting down")


def _check_database_and_seed_users() -> None:
    """Fail fast with a clear message when the database is unreachable or not migrated."""
    try:
        with SessionLocal() as db:
            seed_initial_users(db)
    except OperationalError:
        logger.critical(
            "Cannot connect to the database at %s. Check DATABASE_URL and that PostgreSQL is running.",
            settings.database_url.render_as_string(hide_password=True),
        )
        raise
    except ProgrammingError:
        logger.critical("The database schema is missing or out of date. Run: alembic upgrade head")
        raise


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        lifespan=lifespan,
        openapi_url="/api/v1/docs",
        docs_url="/api/v1/docs/swagger",
        redoc_url=None,
    )
    register_exception_handlers(app)

    # Middleware added last runs first: CORS wraps everything, so even 500 responses carry CORS headers.
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[CORRELATION_ID_HEADER, "Content-Disposition"],
    )

    app.include_router(health.router)
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse("/api/v1/docs/swagger")

    return app


app = create_app()

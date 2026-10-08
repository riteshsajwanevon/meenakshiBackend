"""Spring Actuator-compatible health endpoints (no authentication)."""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import DbSession
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/actuator", tags=["Health"])


@router.get("/health")
@router.get("/health/readiness")
def health(db: DbSession):
    """UP when the database answers; DOWN (503) otherwise."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Health check: database is not reachable")
        return JSONResponse(status_code=503, content={"status": "DOWN", "components": {"db": {"status": "DOWN"}}})
    return {"status": "UP", "components": {"db": {"status": "UP"}}}


@router.get("/health/liveness")
def liveness():
    """The process is running (does not touch the database)."""
    return {"status": "UP"}


@router.get("/info")
def info():
    return {"app": {"name": settings.APP_NAME, "version": settings.APP_VERSION, "environment": settings.ENVIRONMENT}}

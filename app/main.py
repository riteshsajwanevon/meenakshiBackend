from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import models  # noqa: F401  (registers models on Base.metadata)
from app.api.routes import auth
from app.core.config import settings
from app.db.session import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Creates missing tables on startup. Switch to Alembic migrations once the schema starts changing.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)
app.include_router(auth.router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}

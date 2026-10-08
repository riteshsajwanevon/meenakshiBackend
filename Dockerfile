FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SERVER_PORT=8080 \
    FILE_STORAGE_PATH=/data/files

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app

RUN useradd --create-home --uid 1000 appuser && mkdir -p /data/files && chown -R appuser /data
USER appuser

EXPOSE 8080

# Apply pending migrations, then serve. Use several workers in production.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${SERVER_PORT} --workers ${WEB_CONCURRENCY:-2} --proxy-headers"]

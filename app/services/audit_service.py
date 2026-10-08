from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.request_context import get_correlation_id
from app.db.pagination import count_rows, normalize_page
from app.models import AuditLog, User
from app.models.enums import AuditAction, EntityType
from app.schemas.common import PageResponse
from app.schemas.misc import AuditView


def record(
    db: Session,
    *,
    actor: User | None,
    action: AuditAction,
    entity_type: EntityType,
    entity_id: int | str | None = None,
    details: dict | None = None,
) -> None:
    """Add an audit entry to the current transaction (committed together with the change it describes)."""
    db.add(
        AuditLog(
            actor_id=actor.id if actor else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            correlation_id=get_correlation_id(),
            details=details,
        )
    )


def list_logs(db: Session, page: int, size: int) -> PageResponse[AuditView]:
    page, size = normalize_page(page, size)
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    total = count_rows(db, stmt)
    logs = db.scalars(stmt.offset(page * size).limit(size)).all()
    content = [
        AuditView(
            id=log.id,
            actor=log.actor.full_name if log.actor else None,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            correlation_id=log.correlation_id,
            created_at=log.created_at,
        )
        for log in logs
    ]
    return PageResponse[AuditView].of(content, page=page, size=size, total=total)

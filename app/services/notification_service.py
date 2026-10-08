from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError, NotFoundError
from app.models import Notification, User
from app.schemas.misc import NotificationView

RECENT_LIMIT = 30


def notify(db: Session, *, user_id: int, title: str, body: str) -> None:
    """Add a notification to the current transaction."""
    db.add(Notification(user_id=user_id, title=title, body=body))


def list_recent(db: Session, user: User) -> list[NotificationView]:
    notifications = db.scalars(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(RECENT_LIMIT)
    ).all()
    return [NotificationView.model_validate(notification) for notification in notifications]


def mark_read(db: Session, user: User, notification_id: int) -> None:
    notification = db.get(Notification, notification_id)
    if notification is None:
        raise NotFoundError("Notification not found")
    if notification.user_id != user.id:
        raise ForbiddenError("You can only update your own notifications")
    if not notification.read:
        notification.read = True
        db.commit()

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.models import Notification, NotificationType


def create_notification(
    db: Session,
    *,
    user_id: int,
    notification_type: NotificationType | str,
    title: str,
    body: str,
    booking_id: int | None = None,
    message_id: int | None = None,
) -> Notification:
    type_value = (
        notification_type.value
        if isinstance(notification_type, NotificationType)
        else str(notification_type)
    )
    notification = Notification(
        user_id=user_id,
        type=type_value,
        title=title,
        body=body,
        booking_id=booking_id,
        message_id=message_id,
    )
    db.add(notification)
    return notification

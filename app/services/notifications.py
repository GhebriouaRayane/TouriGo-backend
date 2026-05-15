from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.models import Notification, NotificationType
from app.services.push_notifications import send_push_notification_to_user


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


def dispatch_notification_push(db: Session, notification: Notification) -> int:
    return send_push_notification_to_user(
        db,
        user_id=notification.user_id,
        title=notification.title,
        body=notification.body,
        data={
            "notificationId": notification.id,
            "type": notification.type,
            "bookingId": notification.booking_id,
            "messageId": notification.message_id,
        },
    )

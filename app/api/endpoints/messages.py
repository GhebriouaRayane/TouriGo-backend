from __future__ import annotations

from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.api import deps
from app.db.session import get_db
from app.models.models import Booking, Message, NotificationType, User, UserRole
from app.schemas.schemas import MessageCreate, MessageOut
from app.services.notifications import create_notification

router = APIRouter()


def _booking_query_with_relations(db: Session):
    return db.query(Booking).options(
        joinedload(Booking.user),
        joinedload(Booking.listing),
    )


def _message_query_with_relations(db: Session):
    return db.query(Message).options(
        joinedload(Message.sender),
        joinedload(Message.recipient),
        joinedload(Message.booking).joinedload(Booking.listing),
    )


def _get_booking_or_404(db: Session, booking_id: int) -> Booking:
    booking = _booking_query_with_relations(db).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Reservation introuvable.")
    return booking


def _ensure_can_access_booking_messages(current_user: User, booking: Booking) -> None:
    listing_owner_id = booking.listing.owner_id if booking.listing else None
    if current_user.id in {booking.user_id, listing_owner_id}:
        return
    if current_user.role == UserRole.ADMIN.value:
        return
    raise HTTPException(status_code=403, detail="Acces refuse a cette conversation.")


def _resolve_message_recipient(current_user: User, booking: Booking) -> int:
    listing_owner_id = booking.listing.owner_id if booking.listing else None
    if current_user.id == booking.user_id and listing_owner_id:
        return listing_owner_id
    if listing_owner_id == current_user.id and booking.user_id:
        return booking.user_id
    raise HTTPException(
        status_code=403,
        detail="Seuls le client et l'hote peuvent envoyer des messages sur cette reservation.",
    )


@router.get("/bookings/{booking_id}", response_model=List[MessageOut])
def read_booking_messages(
    *,
    db: Session = Depends(get_db),
    booking_id: int,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    booking = _get_booking_or_404(db, booking_id)
    _ensure_can_access_booking_messages(current_user, booking)
    messages = (
        _message_query_with_relations(db)
        .filter(Message.booking_id == booking_id)
        .order_by(Message.created_at.asc(), Message.id.asc())
        .all()
    )
    has_changes = False
    for message in messages:
        if message.recipient_id == current_user.id and not message.is_read:
            message.is_read = True
            db.add(message)
            has_changes = True
    if has_changes:
        db.commit()
    return messages


@router.post(
    "/bookings/{booking_id}",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
)
def send_booking_message(
    *,
    db: Session = Depends(get_db),
    booking_id: int,
    payload: MessageCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    booking = _get_booking_or_404(db, booking_id)
    _ensure_can_access_booking_messages(current_user, booking)
    recipient_id = _resolve_message_recipient(current_user, booking)
    message = Message(
        booking_id=booking.id,
        sender_id=current_user.id,
        recipient_id=recipient_id,
        content=payload.content,
        is_read=False,
    )
    db.add(message)
    db.flush()
    listing_title = booking.listing.title if booking.listing else f"Annonce #{booking.listing_id}"
    create_notification(
        db,
        user_id=recipient_id,
        notification_type=NotificationType.MESSAGE,
        title="Nouveau message",
        body=f"{current_user.full_name or current_user.email} vous a envoye un message au sujet de \"{listing_title}\".",
        booking_id=booking.id,
        message_id=message.id,
    )
    db.commit()
    created = _message_query_with_relations(db).filter(Message.id == message.id).first()
    if not created:
        raise HTTPException(status_code=500, detail="Message cree mais introuvable.")
    return created

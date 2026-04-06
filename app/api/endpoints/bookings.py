from __future__ import annotations

import json
import math
from datetime import date, datetime, time, timedelta
from typing import Any, List, Set

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.api import deps
from app.db.session import get_db
from app.models.models import Booking, BookingStatus, Listing, NotificationType, User, UserRole
from app.schemas.schemas import BookingCreate, BookingOut, BookingRejectPayload
from app.services.notifications import create_notification

router = APIRouter()


def _parse_availability_dates(raw_value: str | None) -> Set[date]:
    if not raw_value:
        return set()
    values: Set[date] = set()
    for part in raw_value.split(","):
        normalized = part.strip()
        if not normalized:
            continue
        values.add(date.fromisoformat(normalized))
    return values


def _iter_requested_days(start: date, end: date) -> Set[date]:
    days: Set[date] = set()
    current = start
    while current < end:
        days.add(current)
        current += timedelta(days=1)
    return days


def _parse_listing_details(raw_value: str | None) -> dict[str, Any]:
    if not raw_value:
        return {}
    try:
        parsed = json.loads(raw_value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    if isinstance(parsed, dict):
        return parsed
    return {}


def _as_positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        if value.is_integer() and value > 0:
            return int(value)
        return None
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        try:
            parsed = int(normalized)
        except ValueError:
            return None
        return parsed if parsed > 0 else None
    return None


def _is_carpool_listing(listing: Listing, details: dict[str, Any]) -> bool:
    if (listing.type or "").strip().lower() != "vehicule":
        return False
    category = (listing.category or "").strip().lower()
    if category == "covoiturage":
        return True
    kind = details.get("kind")
    if isinstance(kind, str) and kind.strip().lower() == "covoiturage":
        return True
    return False


def _is_activity_listing(listing: Listing, details: dict[str, Any]) -> bool:
    listing_type = (listing.type or "").strip().lower()
    if listing_type == "activite":
        return True
    kind = details.get("kind")
    if isinstance(kind, str) and kind.strip().lower() == "activite":
        return True
    return False


def _is_immobilier_listing(listing: Listing) -> bool:
    return (listing.type or "").strip().lower() == "immobilier"


def _extract_carpool_capacity(details: dict[str, Any]) -> int | None:
    return _as_positive_int(details.get("passengers_max")) or _as_positive_int(details.get("seats"))


def _extract_activity_capacity(details: dict[str, Any]) -> int | None:
    return _as_positive_int(details.get("participantsMax")) or _as_positive_int(details.get("participants_max"))


def _extract_immobilier_guest_capacity(listing: Listing, details: dict[str, Any]) -> int | None:
    explicit_capacity = _as_positive_int(details.get("travelers"))
    if explicit_capacity is not None:
        return explicit_capacity
    room_capacity = _as_positive_int(listing.bedrooms)
    if room_capacity is not None:
        return room_capacity * 2
    return None


def _extract_carpool_window(details: dict[str, Any]) -> tuple[datetime, datetime] | None:
    raw_date = details.get("departure_date")
    if not isinstance(raw_date, str):
        return None
    normalized_date = raw_date.strip()
    if not normalized_date:
        return None
    try:
        departure_date = date.fromisoformat(normalized_date)
    except ValueError:
        return None

    departure_time = time(0, 0, 0)
    raw_time = details.get("departure_time")
    if isinstance(raw_time, str):
        normalized_time = raw_time.strip()
        if normalized_time:
            for time_format in ("%H:%M", "%H:%M:%S"):
                try:
                    departure_time = datetime.strptime(normalized_time, time_format).time()
                    break
                except ValueError:
                    continue

    start = datetime.combine(departure_date, departure_time)
    end = start + timedelta(hours=1)
    return start, end


def _booking_query_with_relations(db: Session):
    return db.query(Booking).options(
        joinedload(Booking.user),
        joinedload(Booking.listing).joinedload(Listing.owner),
    )


def _get_booking_with_listing(db: Session, booking_id: int) -> Booking:
    booking = _booking_query_with_relations(db).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Reservation introuvable.")
    return booking


def _ensure_host_can_manage_booking(current_user: User, booking: Booking) -> None:
    if current_user.role == UserRole.ADMIN.value:
        return
    if current_user.role != UserRole.HOST.value:
        raise HTTPException(status_code=403, detail="Seuls les hotes peuvent gerer les reservations recues.")
    listing_owner_id = booking.listing.owner_id if booking.listing else None
    if listing_owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Vous ne pouvez gerer que les reservations de vos annonces.")


def _ensure_pending_booking(booking: Booking) -> None:
    if booking.status != BookingStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="Cette reservation a deja ete traitee.")


def _ensure_client_can_cancel_booking(current_user: User, booking: Booking) -> None:
    if current_user.role == UserRole.ADMIN.value:
        return
    if booking.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Vous ne pouvez annuler que vos propres reservations.")


def _ensure_cancellable_booking(booking: Booking) -> None:
    if booking.status not in {BookingStatus.PENDING.value, BookingStatus.CONFIRMED.value}:
        raise HTTPException(status_code=400, detail="Seules les reservations en attente ou confirmees peuvent etre annulees.")


@router.get("/me", response_model=List[BookingOut])
def read_my_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    bookings = _booking_query_with_relations(db).filter(Booking.user_id == current_user.id).order_by(Booking.start_date.desc()).all()
    return bookings


@router.get("/received", response_model=List[BookingOut])
def read_received_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    query = _booking_query_with_relations(db)
    if current_user.role == UserRole.ADMIN.value:
        bookings = query.order_by(Booking.start_date.desc()).all()
    elif current_user.role == UserRole.HOST.value:
        bookings = (
            query.join(Booking.listing)
            .filter(Listing.owner_id == current_user.id)
            .order_by(Booking.start_date.desc())
            .all()
        )
    else:
        raise HTTPException(status_code=403, detail="Seuls les hotes peuvent consulter les reservations recues.")
    return bookings


@router.post(
    "/",
    response_model=BookingOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Bad Request"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
        409: {"description": "Conflict"},
    },
)
def create_booking(
    *,
    db: Session = Depends(get_db),
    booking_in: BookingCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    listing = db.query(Listing).filter(Listing.id == booking_in.listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Annonce introuvable.")
    if listing.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas reserver votre propre annonce.")
    listing_details = _parse_listing_details(listing.details)
    is_carpool = _is_carpool_listing(listing, listing_details)
    is_activity = _is_activity_listing(listing, listing_details)
    is_immobilier = _is_immobilier_listing(listing)
    booking_start = booking_in.start_date
    booking_end = booking_in.end_date
    seats_reserved: int | None = None
    rooms_reserved: int | None = None
    guests_reserved: int | None = None

    if is_carpool:
        if booking_in.rooms_reserved is not None or booking_in.guests_reserved is not None:
            raise HTTPException(
                status_code=400,
                detail="Les chambres et personnes reservees sont uniquement disponibles pour l'immobilier.",
            )
        seats_reserved = booking_in.seats_reserved or 1
        if seats_reserved <= 0:
            raise HTTPException(status_code=400, detail="Le nombre de places reservees doit etre superieur a 0.")

        window = _extract_carpool_window(listing_details)
        if window is not None:
            booking_start, booking_end = window
        elif booking_start is None or booking_end is None:
            raise HTTPException(
                status_code=400,
                detail="Les champs start_date et end_date sont obligatoires pour ce trajet.",
            )

        capacity = _extract_carpool_capacity(listing_details)
        if capacity is not None and seats_reserved > capacity:
            raise HTTPException(
                status_code=400,
                detail=f"Le trajet ne propose que {capacity} place(s).",
            )

        overlapping_bookings = (
            db.query(Booking)
            .filter(
                Booking.listing_id == booking_in.listing_id,
                Booking.status.in_([BookingStatus.PENDING.value, BookingStatus.CONFIRMED.value]),
                Booking.start_date < booking_end,
                Booking.end_date > booking_start,
            )
            .all()
        )
        if capacity is None:
            if overlapping_bookings:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Ce trajet n'est plus disponible.",
                )
        else:
            already_reserved = sum(max(1, booking.seats_reserved or 1) for booking in overlapping_bookings)
            available = capacity - already_reserved
            if available < seats_reserved:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Places insuffisantes. Il reste {max(0, available)} place(s).",
                )
    elif is_activity:
        if booking_in.rooms_reserved is not None or booking_in.guests_reserved is not None:
            raise HTTPException(
                status_code=400,
                detail="Les chambres et personnes reservees sont uniquement disponibles pour l'immobilier.",
            )
        seats_reserved = booking_in.seats_reserved or 1
        if seats_reserved <= 0:
            raise HTTPException(status_code=400, detail="Le nombre de participants doit etre superieur a 0.")

        if booking_in.start_date is None:
            raise HTTPException(
                status_code=400,
                detail="Le champ start_date est obligatoire pour cette activite.",
            )
        booking_start = booking_in.start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        booking_end = booking_start + timedelta(days=1)

        capacity = _extract_activity_capacity(listing_details)
        overlapping_bookings = (
            db.query(Booking)
            .filter(
                Booking.listing_id == booking_in.listing_id,
                Booking.status.in_([BookingStatus.PENDING.value, BookingStatus.CONFIRMED.value]),
                Booking.start_date < booking_end,
                Booking.end_date > booking_start,
            )
            .all()
        )
        if capacity is None:
            if overlapping_bookings:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cette date n'est plus disponible.",
                )
        else:
            already_reserved = sum(max(1, booking.seats_reserved or 1) for booking in overlapping_bookings)
            available = capacity - already_reserved
            if available < seats_reserved:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Participants insuffisants. Il reste {max(0, available)} place(s).",
                )
    elif is_immobilier:
        if booking_start is None or booking_end is None:
            raise HTTPException(
                status_code=400,
                detail="Les champs start_date et end_date sont obligatoires pour l'immobilier.",
            )
        if booking_in.seats_reserved is not None:
            raise HTTPException(
                status_code=400,
                detail="Le nombre reserve est uniquement disponible pour le covoiturage et les activites.",
            )
        rooms_reserved = booking_in.rooms_reserved or 1
        guests_reserved = booking_in.guests_reserved or 1
        if rooms_reserved <= 0:
            raise HTTPException(status_code=400, detail="Le nombre de chambres reservees doit etre superieur a 0.")
        if guests_reserved <= 0:
            raise HTTPException(status_code=400, detail="Le nombre de personnes doit etre superieur a 0.")

        room_capacity = _as_positive_int(listing.bedrooms)
        if room_capacity is not None and rooms_reserved > room_capacity:
            raise HTTPException(
                status_code=400,
                detail=f"Cette annonce propose au maximum {room_capacity} chambre(s).",
            )
        guests_capacity = _extract_immobilier_guest_capacity(listing, listing_details)
        if guests_capacity is not None and guests_reserved > guests_capacity:
            raise HTTPException(
                status_code=400,
                detail=f"Cette annonce accepte au maximum {guests_capacity} personne(s).",
            )

        overlapping_bookings = (
            db.query(Booking)
            .filter(
                Booking.listing_id == booking_in.listing_id,
                Booking.status.in_([BookingStatus.PENDING.value, BookingStatus.CONFIRMED.value]),
                Booking.start_date < booking_end,
                Booking.end_date > booking_start,
            )
            .all()
        )
        if room_capacity is None:
            if overlapping_bookings:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Ces dates ne sont plus disponibles.",
                )
        else:
            already_reserved_rooms = sum(max(1, booking.rooms_reserved or 1) for booking in overlapping_bookings)
            available_rooms = room_capacity - already_reserved_rooms
            if available_rooms < rooms_reserved:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Chambres insuffisantes. Il reste {max(0, available_rooms)} chambre(s).",
                )
    else:
        if booking_start is None or booking_end is None:
            raise HTTPException(
                status_code=400,
                detail="Les champs start_date et end_date sont obligatoires pour cette annonce.",
            )
        if (
            booking_in.seats_reserved is not None
            or booking_in.rooms_reserved is not None
            or booking_in.guests_reserved is not None
        ):
            raise HTTPException(
                status_code=400,
                detail="Le nombre reserve n'est pas pris en charge pour ce type d'annonce.",
            )
        conflict = (
            db.query(Booking)
            .filter(
                Booking.listing_id == booking_in.listing_id,
                Booking.status.in_([BookingStatus.PENDING.value, BookingStatus.CONFIRMED.value]),
                Booking.start_date < booking_end,
                Booking.end_date > booking_start,
            )
            .first()
        )
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ces dates ne sont plus disponibles.",
            )

    if booking_start is None or booking_end is None:
        raise HTTPException(status_code=400, detail="Plage de reservation invalide.")

    if not is_carpool:
        try:
            available_dates = _parse_availability_dates(listing.availability_dates)
        except ValueError:
            available_dates = set()
        if available_dates:
            requested_dates = _iter_requested_days(booking_start.date(), booking_end.date())
            missing_dates = sorted(requested_dates - available_dates)
            if missing_dates:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "La reservation doit respecter les dates de disponibilite de l'hote. "
                        f"Dates indisponibles: {', '.join(day.isoformat() for day in missing_dates[:6])}"
                    ),
                )

    if is_carpool or is_activity:
        total_price = float((seats_reserved or 1) * listing.price)
    elif is_immobilier:
        duration_seconds = (booking_end - booking_start).total_seconds()
        duration_units = max(1, math.ceil(duration_seconds / 86400))
        total_price = float(duration_units * listing.price * (rooms_reserved or 1))
    else:
        duration_seconds = (booking_end - booking_start).total_seconds()
        duration_units = max(1, math.ceil(duration_seconds / 86400))
        total_price = float(duration_units * listing.price)

    booking = Booking(
        start_date=booking_start,
        end_date=booking_end,
        listing_id=booking_in.listing_id,
        user_id=current_user.id,
        total_price=total_price,
        seats_reserved=seats_reserved,
        rooms_reserved=rooms_reserved,
        guests_reserved=guests_reserved,
        status=BookingStatus.PENDING.value,
    )
    db.add(booking)
    db.flush()
    if listing.owner_id:
        if is_carpool:
            booking_date = booking_start.date().isoformat()
            booking_time = booking_start.strftime("%H:%M")
            seat_label = f"{seats_reserved} place(s)"
            body = (
                f"{current_user.full_name or current_user.email} a reserve {seat_label} pour "
                f"\"{listing.title}\" le {booking_date} a {booking_time}."
            )
        elif is_activity:
            booking_date = booking_start.date().isoformat()
            participant_label = f"{seats_reserved} participant(s)"
            body = (
                f"{current_user.full_name or current_user.email} a reserve {participant_label} pour "
                f"\"{listing.title}\" le {booking_date}."
            )
        elif is_immobilier:
            rooms_label = f"{rooms_reserved} chambre(s)"
            guests_label = f"{guests_reserved} personne(s)"
            body = (
                f"{current_user.full_name or current_user.email} a demande la reservation de {rooms_label} "
                f"pour {guests_label} sur \"{listing.title}\" du {booking_start.date().isoformat()} "
                f"au {booking_end.date().isoformat()}."
            )
        else:
            body = (
                f"{current_user.full_name or current_user.email} a demande la reservation de "
                f"\"{listing.title}\" du {booking_start.date().isoformat()} "
                f"au {booking_end.date().isoformat()}."
            )
        create_notification(
            db,
            user_id=listing.owner_id,
            notification_type=NotificationType.BOOKING_REQUEST,
            title="Nouvelle demande de reservation",
            body=body,
            booking_id=booking.id,
        )
    db.commit()
    return _get_booking_with_listing(db, booking.id)


@router.post("/{booking_id}/confirm", response_model=BookingOut)
def confirm_booking(
    *,
    db: Session = Depends(get_db),
    booking_id: int,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    booking = _get_booking_with_listing(db, booking_id)
    _ensure_host_can_manage_booking(current_user, booking)
    _ensure_pending_booking(booking)
    booking.status = BookingStatus.CONFIRMED.value
    db.add(booking)
    if booking.user_id:
        listing_title = booking.listing.title if booking.listing else f"Annonce #{booking.listing_id}"
        create_notification(
            db,
            user_id=booking.user_id,
            notification_type=NotificationType.BOOKING_STATUS,
            title="Reservation confirmee",
            body=f"Votre reservation pour \"{listing_title}\" a ete confirmee par l'hote.",
            booking_id=booking.id,
        )
    db.commit()
    return _get_booking_with_listing(db, booking.id)


@router.post("/{booking_id}/reject", response_model=BookingOut)
def reject_booking(
    *,
    db: Session = Depends(get_db),
    booking_id: int,
    payload: BookingRejectPayload,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    booking = _get_booking_with_listing(db, booking_id)
    _ensure_host_can_manage_booking(current_user, booking)
    _ensure_pending_booking(booking)
    booking.status = BookingStatus.REJECTED.value
    db.add(booking)
    if booking.user_id:
        listing_title = booking.listing.title if booking.listing else f"Annonce #{booking.listing_id}"
        reason = payload.reason.strip() if payload.reason else ""
        rejection_suffix = f" Motif: {reason}" if reason else ""
        create_notification(
            db,
            user_id=booking.user_id,
            notification_type=NotificationType.BOOKING_STATUS,
            title="Reservation refusee",
            body=f"Votre reservation pour \"{listing_title}\" a ete refusee par l'hote.{rejection_suffix}",
            booking_id=booking.id,
        )
    db.commit()
    return _get_booking_with_listing(db, booking.id)


@router.post("/{booking_id}/cancel", response_model=BookingOut)
def cancel_booking(
    *,
    db: Session = Depends(get_db),
    booking_id: int,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    booking = _get_booking_with_listing(db, booking_id)
    _ensure_client_can_cancel_booking(current_user, booking)
    _ensure_cancellable_booking(booking)
    booking.status = BookingStatus.CANCELLED.value
    db.add(booking)
    listing_owner_id = booking.listing.owner_id if booking.listing else None
    if listing_owner_id and listing_owner_id != current_user.id:
        listing_title = booking.listing.title if booking.listing else f"Annonce #{booking.listing_id}"
        create_notification(
            db,
            user_id=listing_owner_id,
            notification_type=NotificationType.BOOKING_STATUS,
            title="Reservation annulee",
            body=f"Le client a annule sa reservation pour \"{listing_title}\".",
            booking_id=booking.id,
        )
    db.commit()
    return _get_booking_with_listing(db, booking.id)

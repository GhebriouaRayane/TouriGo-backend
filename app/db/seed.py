from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.models import Booking, BookingStatus, Favorite, Listing, ListingImage, ListingType, Review, User, UserRole


def _ensure_user(
    db: Session,
    *,
    email: str,
    full_name: str,
    password: str,
    phone_number: str | None = None,
    role: str = UserRole.USER.value,
) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user:
        if phone_number and user.phone_number != phone_number:
            user.phone_number = phone_number
            db.add(user)
            db.flush()
        return user
    user = User(
        email=email,
        full_name=full_name,
        hashed_password=get_password_hash(password),
        phone_number=phone_number,
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _ensure_listing(
    db: Session,
    *,
    owner_id: int,
    title: str,
    type_value: str,
    category: str,
    location: str,
    price: float,
    period: str,
    description: str,
    bedrooms: int | None = None,
    bathrooms: int | None = None,
    area: float | None = None,
    availability_dates: str | None = None,
    image_urls: list[str] | None = None,
) -> Listing:
    listing = db.query(Listing).filter(Listing.title == title, Listing.owner_id == owner_id).first()
    if listing:
        return listing
    listing = Listing(
        owner_id=owner_id,
        title=title,
        type=type_value,
        category=category,
        location=location,
        price=price,
        period=period,
        description=description,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        area=area,
        availability_dates=availability_dates,
    )
    db.add(listing)
    db.flush()
    for url in image_urls or []:
        db.add(ListingImage(url=url, listing_id=listing.id))
    db.flush()
    return listing


def seed_database(db: Session) -> None:
    admin = _ensure_user(
        db,
        email="admin@3ich.app",
        full_name="Admin 3ich",
        password="AdminPassword123!",
        role=UserRole.ADMIN.value,
    )
    host_karim = _ensure_user(
        db,
        email="karim@3ich.app",
        full_name="Karim Mansouri",
        password="HostPassword123!",
        phone_number="+213 555 12 34 56",
        role=UserRole.HOST.value,
    )
    host_samira = _ensure_user(
        db,
        email="samira@3ich.app",
        full_name="Samira Bensaid",
        password="HostPassword123!",
        phone_number="+213 555 98 76 54",
        role=UserRole.HOST.value,
    )
    user_amina = _ensure_user(
        db,
        email="amina@3ich.app",
        full_name="Amina Belaid",
        password="UserPassword123!",
    )
    user_yacine = _ensure_user(
        db,
        email="yacine@3ich.app",
        full_name="Yacine Ait",
        password="UserPassword123!",
    )

    listing_1 = _ensure_listing(
        db,
        owner_id=host_karim.id,
        title="Villa moderne avec piscine privee",
        type_value=ListingType.IMMOBILIER.value,
        category="maison",
        location="Hydra, Alger",
        price=45000,
        period="nuit",
        bedrooms=4,
        bathrooms=3,
        area=250,
        availability_dates="2026-02-20,2026-02-21,2026-02-22,2026-02-23,2026-02-24",
        description="Villa familiale haut standing avec piscine et terrasse.",
        image_urls=[
            "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=800",
            "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=800",
        ],
    )
    listing_2 = _ensure_listing(
        db,
        owner_id=host_samira.id,
        title="Appartement centre ville lumineux",
        type_value=ListingType.IMMOBILIER.value,
        category="appartement",
        location="Oran Centre, Oran",
        price=25000,
        period="nuit",
        bedrooms=2,
        bathrooms=1,
        area=85,
        availability_dates="2026-02-18,2026-02-19,2026-02-20,2026-02-21",
        description="Appartement equipe proche des transports et commerces.",
        image_urls=[
            "https://images.unsplash.com/photo-1484154218962-a197022b5858?w=800",
        ],
    )
    listing_5 = _ensure_listing(
        db,
        owner_id=host_samira.id,
        title="Hotel bord de mer avec spa",
        type_value=ListingType.IMMOBILIER.value,
        category="hotel",
        location="Sidi Fredj, Alger",
        price=32000,
        period="nuit",
        bedrooms=22,
        bathrooms=12,
        area=None,
        availability_dates="2026-02-20,2026-02-21,2026-02-22,2026-02-23,2026-02-24",
        description="Hotel confortable avec vue mer, petit-dejeuner inclus et espace bien-etre.",
        image_urls=[
            "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=800",
            "https://images.unsplash.com/photo-1445019980597-93fa8acb246c?w=800",
        ],
    )
    listing_6 = _ensure_listing(
        db,
        owner_id=host_karim.id,
        title="Cabanon familial proche plage",
        type_value=ListingType.IMMOBILIER.value,
        category="cabanon",
        location="Ain Taya, Alger",
        price=17000,
        period="nuit",
        bedrooms=2,
        bathrooms=1,
        area=68,
        availability_dates="2026-02-19,2026-02-20,2026-02-21,2026-02-22",
        description="Cabanon equipe a quelques minutes de la plage, ideal pour un sejour en famille.",
        image_urls=[
            "https://images.unsplash.com/photo-1499793983690-e29da59ef1c2?w=800",
            "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?w=800",
        ],
    )
    listing_3 = _ensure_listing(
        db,
        owner_id=host_karim.id,
        title="BMW Serie 5 - confort premium",
        type_value=ListingType.VEHICULE.value,
        category="location",
        location="Constantine",
        price=8000,
        period="jour",
        availability_dates="2026-02-16,2026-02-17,2026-02-18,2026-02-19",
        description="Berline premium bien entretenue, ideal trajets business.",
        image_urls=[
            "https://images.unsplash.com/photo-1614200179396-2bdb77ebf81b?w=800",
        ],
    )
    listing_4 = _ensure_listing(
        db,
        owner_id=host_samira.id,
        title="Bapteme plongee sous-marine",
        type_value=ListingType.ACTIVITE.value,
        category="nautique",
        location="Tipaza",
        price=6500,
        period="personne",
        availability_dates="2026-02-22,2026-02-23,2026-02-24",
        description="Initiation a la plongee encadree par moniteur certifie.",
        image_urls=[
            "https://images.unsplash.com/photo-1544551763-46a013bb70d5?w=800",
        ],
    )

    # Reviews (idempotent per user/listing)
    for user, listing, rating, comment in [
        (user_amina, listing_1, 5, "Sejour excellent, logement impeccable."),
        (user_yacine, listing_1, 4, "Tres bon accueil et emplacement pratique."),
        (user_amina, listing_5, 5, "Excellent hotel, personnel tres professionnel."),
        (user_yacine, listing_5, 4, "Belle vue et chambre confortable, je recommande."),
        (user_amina, listing_6, 5, "Cabanon tres propre et bien situe pour la plage."),
        (user_yacine, listing_6, 4, "Sejour agreable en famille, quartier calme."),
        (user_amina, listing_3, 5, "Vehicule propre et ponctualite parfaite."),
    ]:
        existing = (
            db.query(Review)
            .filter(Review.user_id == user.id, Review.listing_id == listing.id)
            .first()
        )
        if not existing:
            db.add(
                Review(
                    user_id=user.id,
                    listing_id=listing.id,
                    rating=rating,
                    comment=comment,
                )
            )

    # Favorites (idempotent)
    for user, listing in [
        (user_amina, listing_1),
        (user_amina, listing_4),
        (user_yacine, listing_2),
    ]:
        existing = (
            db.query(Favorite)
            .filter(Favorite.user_id == user.id, Favorite.listing_id == listing.id)
            .first()
        )
        if not existing:
            db.add(Favorite(user_id=user.id, listing_id=listing.id))

    # Bookings (idempotent by user/listing/start_date)
    start_date = datetime.now(timezone.utc).replace(microsecond=0)
    bookings = [
        (
            user_amina,
            listing_1,
            start_date + timedelta(days=7),
            start_date + timedelta(days=11),
            180000.0,
            BookingStatus.CONFIRMED.value,
        ),
        (
            user_yacine,
            listing_3,
            start_date + timedelta(days=3),
            start_date + timedelta(days=5),
            16000.0,
            BookingStatus.PENDING.value,
        ),
    ]
    for user, listing, start, end, total, status in bookings:
        existing = (
            db.query(Booking)
            .filter(
                Booking.user_id == user.id,
                Booking.listing_id == listing.id,
                Booking.start_date == start,
            )
            .first()
        )
        if not existing:
            db.add(
                Booking(
                    user_id=user.id,
                    listing_id=listing.id,
                    start_date=start,
                    end_date=end,
                    total_price=total,
                    status=status,
                )
            )

    db.commit()

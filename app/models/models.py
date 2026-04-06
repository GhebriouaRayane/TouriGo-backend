from __future__ import annotations

from datetime import datetime
import enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.session import Base


class UserRole(str, enum.Enum):
    USER = "user"
    HOST = "host"
    ADMIN = "admin"


class ListingType(str, enum.Enum):
    IMMOBILIER = "immobilier"
    VEHICULE = "vehicule"
    ACTIVITE = "activite"


class BookingStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class NotificationType(str, enum.Enum):
    BOOKING_REQUEST = "booking_request"
    BOOKING_STATUS = "booking_status"
    MESSAGE = "message"


class VerificationChannel(str, enum.Enum):
    EMAIL = "email"
    PHONE = "phone"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(String, default=UserRole.USER.value)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    listings: Mapped[list["Listing"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    bookings: Mapped[list["Booking"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    reviews: Mapped[list["Review"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    favorites: Mapped[list["Favorite"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    sent_messages: Mapped[list["Message"]] = relationship(
        foreign_keys="Message.sender_id",
        back_populates="sender",
        cascade="all, delete-orphan",
    )
    received_messages: Mapped[list["Message"]] = relationship(
        foreign_keys="Message.recipient_id",
        back_populates="recipient",
        cascade="all, delete-orphan",
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (
        CheckConstraint("price > 0", name="ck_listings_price_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(String, nullable=False)  # ListingType
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    location: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    period: Mapped[str | None] = mapped_column(String, nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    availability_dates: Mapped[str | None] = mapped_column(Text, nullable=True)

    bedrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bathrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    area: Mapped[float | None] = mapped_column(Float, nullable=True)
    owner_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    owner: Mapped["User"] = relationship(back_populates="listings")

    images: Mapped[list["ListingImage"]] = relationship(
        back_populates="listing", cascade="all, delete-orphan"
    )
    bookings: Mapped[list["Booking"]] = relationship(
        back_populates="listing", cascade="all, delete-orphan"
    )
    reviews: Mapped[list["Review"]] = relationship(
        back_populates="listing", cascade="all, delete-orphan"
    )
    favorites: Mapped[list["Favorite"]] = relationship(
        back_populates="listing", cascade="all, delete-orphan"
    )

    @property
    def owner_full_name(self) -> str | None:
        if not self.owner:
            return None
        return self.owner.full_name

    @property
    def owner_phone_number(self) -> str | None:
        if not self.owner:
            return None
        return self.owner.phone_number


class ListingImage(Base):
    __tablename__ = "listing_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    url: Mapped[str] = mapped_column(String, nullable=False)
    listing_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("listings.id"))
    listing: Mapped["Listing"] = relationship(back_populates="images")


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("total_price IS NULL OR total_price >= 0", name="ck_bookings_total_price_non_negative"),
        CheckConstraint("seats_reserved IS NULL OR seats_reserved > 0", name="ck_bookings_seats_reserved_positive"),
        CheckConstraint("rooms_reserved IS NULL OR rooms_reserved > 0", name="ck_bookings_rooms_reserved_positive"),
        CheckConstraint("guests_reserved IS NULL OR guests_reserved > 0", name="ck_bookings_guests_reserved_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    seats_reserved: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rooms_reserved: Mapped[int | None] = mapped_column(Integer, nullable=True)
    guests_reserved: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String, default=BookingStatus.PENDING.value)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    listing_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("listings.id"))

    user: Mapped["User"] = relationship(back_populates="bookings")
    listing: Mapped["Listing"] = relationship(back_populates="bookings")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="booking", cascade="all, delete-orphan"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="booking", cascade="all, delete-orphan"
    )

    @property
    def listing_title(self) -> str | None:
        if not self.listing:
            return None
        return self.listing.title

    @property
    def listing_location(self) -> str | None:
        if not self.listing:
            return None
        return self.listing.location

    @property
    def requester_full_name(self) -> str | None:
        if not self.user:
            return None
        return self.user.full_name

    @property
    def requester_email(self) -> str | None:
        if not self.user:
            return None
        return self.user.email

    @property
    def host_id(self) -> int | None:
        if not self.listing:
            return None
        return self.listing.owner_id

    @property
    def host_full_name(self) -> str | None:
        if not self.listing or not self.listing.owner:
            return None
        return self.listing.owner.full_name


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    booking_id: Mapped[int] = mapped_column(Integer, ForeignKey("bookings.id"), nullable=False, index=True)
    sender_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    recipient_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    booking: Mapped["Booking"] = relationship(back_populates="messages")
    sender: Mapped["User"] = relationship(foreign_keys=[sender_id], back_populates="sent_messages")
    recipient: Mapped["User"] = relationship(foreign_keys=[recipient_id], back_populates="received_messages")
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )

    @property
    def sender_name(self) -> str | None:
        if not self.sender:
            return None
        return self.sender.full_name or self.sender.email

    @property
    def recipient_name(self) -> str | None:
        if not self.recipient:
            return None
        return self.recipient.full_name or self.recipient.email

    @property
    def listing_id(self) -> int | None:
        if not self.booking:
            return None
        return self.booking.listing_id

    @property
    def listing_title(self) -> str | None:
        if not self.booking or not self.booking.listing:
            return None
        return self.booking.listing.title


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    booking_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("bookings.id"), nullable=True, index=True)
    message_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("messages.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="notifications")
    booking: Mapped["Booking | None"] = relationship(back_populates="notifications")
    message: Mapped["Message | None"] = relationship(back_populates="notifications")


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("user_id", "listing_id", name="uq_reviews_user_listing"),
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_reviews_rating_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    listing_id: Mapped[int] = mapped_column(Integer, ForeignKey("listings.id"), nullable=False, index=True)

    user: Mapped["User"] = relationship(back_populates="reviews")
    listing: Mapped["Listing"] = relationship(back_populates="reviews")

    @property
    def user_full_name(self) -> str | None:
        if not self.user:
            return None
        return self.user.full_name or self.user.email


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "listing_id", name="uq_favorites_user_listing"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    listing_id: Mapped[int] = mapped_column(Integer, ForeignKey("listings.id"), nullable=False, index=True)

    user: Mapped["User"] = relationship(back_populates="favorites")
    listing: Mapped["Listing"] = relationship(back_populates="favorites")


class RegistrationCode(Base):
    __tablename__ = "registration_codes"
    __table_args__ = (
        CheckConstraint("attempts >= 0", name="ck_registration_codes_attempts_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, nullable=False, index=True)
    phone_number: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, default=UserRole.USER.value, nullable=False)
    channel: Mapped[str] = mapped_column(String, nullable=False)
    hashed_code: Mapped[str] = mapped_column(String, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

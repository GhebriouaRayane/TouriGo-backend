from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
from app.models.models import BookingStatus, ListingType, NotificationType, UserRole, VerificationChannel

# --- User Schemas ---
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    phone_number: Optional[str] = None
    role: str = UserRole.USER.value
    model_config = ConfigDict(extra="forbid")

class UserCreate(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    phone_number: Optional[str] = None
    password: str = Field(min_length=8, max_length=128)
    model_config = ConfigDict(extra="forbid")

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    phone_number: Optional[str] = None
    model_config = ConfigDict(extra="forbid")

class UserPasswordUpdate(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
    model_config = ConfigDict(extra="forbid")

class UserDelete(BaseModel):
    password: str = Field(min_length=8, max_length=128)
    model_config = ConfigDict(extra="forbid")

class UserOut(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RegisterCodeRequest(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    phone_number: Optional[str] = None
    password: str = Field(min_length=8, max_length=128)
    become_host: bool = False
    channel: VerificationChannel = VerificationChannel.EMAIL
    model_config = ConfigDict(extra="forbid")

    @field_validator("phone_number")
    @classmethod
    def normalize_phone_number(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        return normalized

    @model_validator(mode="after")
    def validate_channel_target(self) -> "RegisterCodeRequest":
        if self.channel == VerificationChannel.PHONE and not self.phone_number:
            raise ValueError("Le numero de telephone est obligatoire.")
        if self.channel == VerificationChannel.EMAIL and not self.email:
            raise ValueError("L'email est obligatoire pour l'inscription par email.")
        return self


class RegisterCodeRequestOut(BaseModel):
    verification_id: int
    message: str
    channel: VerificationChannel
    target: str
    expires_at: datetime
    debug_code: Optional[str] = None


class RegisterCodeVerify(BaseModel):
    verification_id: int = Field(gt=0)
    code: str = Field(min_length=4, max_length=10)
    model_config = ConfigDict(extra="forbid")

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.isdigit():
            raise ValueError("Le code de verification doit contenir uniquement des chiffres.")
        return normalized

# --- Token Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    sub: Optional[str] = None
    exp: Optional[int] = None


class GoogleLoginRequest(BaseModel):
    id_token: str = Field(min_length=20)
    model_config = ConfigDict(extra="forbid")

# --- Listing Schemas ---
class ListingImageBase(BaseModel):
    url: str

class ListingImageOut(ListingImageBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class ListingBase(BaseModel):
    title: str
    description: Optional[str] = None
    type: ListingType
    category: Optional[str] = None
    location: str
    price: float = Field(gt=0)
    period: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    area: Optional[float] = None
    details: Optional[str] = None
    availability_dates: Optional[str] = None
    model_config = ConfigDict(extra="forbid")

    @field_validator("availability_dates")
    @classmethod
    def normalize_availability_dates(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        parts = [part.strip() for part in normalized.split(",") if part.strip()]
        if not parts:
            return None
        dates: List[str] = []
        for part in parts:
            try:
                parsed = date.fromisoformat(part)
            except ValueError as exc:
                raise ValueError("Le format de disponibilite doit etre YYYY-MM-DD separe par des virgules.") from exc
            dates.append(parsed.isoformat())
        return ",".join(sorted(set(dates)))

class ListingCreate(ListingBase):
    image_urls: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_by_type(self) -> "ListingCreate":
        if self.type == ListingType.IMMOBILIER:
            normalized_category = (self.category or "").strip().lower()
            is_hotel_category = normalized_category in {"hotel", "hôtel"}
            if self.bedrooms is None or self.bathrooms is None or (not is_hotel_category and self.area is None):
                raise ValueError("Pour une annonce immobilier, chambres et salles de bain sont obligatoires. La surface est obligatoire sauf pour hotel.")
        if self.type in {ListingType.VEHICULE, ListingType.ACTIVITE}:
            if not self.details or not self.details.strip():
                raise ValueError("Le champ details est obligatoire pour les annonces vehicule et activite.")
        return self


class ListingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    type: Optional[ListingType] = None
    category: Optional[str] = None
    location: Optional[str] = None
    price: Optional[float] = Field(default=None, gt=0)
    period: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    area: Optional[float] = None
    details: Optional[str] = None
    availability_dates: Optional[str] = None
    image_urls: Optional[List[str]] = None
    model_config = ConfigDict(extra="forbid")

    @field_validator("availability_dates")
    @classmethod
    def normalize_availability_dates(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        parts = [part.strip() for part in normalized.split(",") if part.strip()]
        if not parts:
            return None
        dates: List[str] = []
        for part in parts:
            try:
                parsed = date.fromisoformat(part)
            except ValueError as exc:
                raise ValueError("Le format de disponibilite doit etre YYYY-MM-DD separe par des virgules.") from exc
            dates.append(parsed.isoformat())
        return ",".join(sorted(set(dates)))

class ListingOut(ListingBase):
    id: int
    owner_id: Optional[int] = None
    owner_full_name: Optional[str] = None
    owner_phone_number: Optional[str] = None
    images: List[ListingImageOut] = []
    model_config = ConfigDict(from_attributes=True)

# --- Booking Schemas ---
class BookingBase(BaseModel):
    start_date: datetime
    end_date: datetime
    listing_id: int
    seats_reserved: Optional[int] = Field(default=None, gt=0)
    rooms_reserved: Optional[int] = Field(default=None, gt=0)
    guests_reserved: Optional[int] = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_date_range(self) -> "BookingBase":
        if self.end_date <= self.start_date:
            raise ValueError("La date de fin doit etre apres la date de debut.")
        return self

class BookingCreate(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    listing_id: int
    seats_reserved: Optional[int] = Field(default=None, gt=0)
    rooms_reserved: Optional[int] = Field(default=None, gt=0)
    guests_reserved: Optional[int] = Field(default=None, gt=0)
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_date_range(self) -> "BookingCreate":
        if (self.start_date is None) != (self.end_date is None):
            raise ValueError("Les champs start_date et end_date doivent etre fournis ensemble.")
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            raise ValueError("La date de fin doit etre apres la date de debut.")
        return self


class BookingRejectPayload(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=300)
    model_config = ConfigDict(extra="forbid")


class BookingOut(BookingBase):
    id: int
    user_id: int
    total_price: float
    status: BookingStatus
    listing_title: Optional[str] = None
    listing_location: Optional[str] = None
    requester_full_name: Optional[str] = None
    requester_email: Optional[str] = None
    host_id: Optional[int] = None
    host_full_name: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class NotificationOut(BaseModel):
    id: int
    user_id: int
    type: NotificationType
    title: str
    body: str
    is_read: bool
    booking_id: Optional[int] = None
    message_id: Optional[int] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class NotificationReadAllResponse(BaseModel):
    updated: int = Field(ge=0)
    model_config = ConfigDict(extra="forbid")


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    model_config = ConfigDict(extra="forbid")

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Le message ne peut pas etre vide.")
        return normalized


class MessageOut(BaseModel):
    id: int
    booking_id: int
    sender_id: int
    recipient_id: int
    content: str
    is_read: bool
    created_at: datetime
    sender_name: Optional[str] = None
    recipient_name: Optional[str] = None
    listing_id: Optional[int] = None
    listing_title: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

# --- Review Schemas ---
class ReviewBase(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = None

class ReviewCreate(ReviewBase):
    listing_id: int

class ReviewOut(ReviewBase):
    id: int
    user_id: int
    listing_id: int
    user_full_name: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# --- Favorite Schemas ---
class FavoriteCreate(BaseModel):
    listing_id: int

class FavoriteOut(BaseModel):
    id: int
    user_id: int
    listing_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    message: str


class UploadAvatarResponse(BaseModel):
    url: str
    model_config = ConfigDict(extra="forbid")


class UploadListingImagesResponse(BaseModel):
    urls: List[str]
    model_config = ConfigDict(extra="forbid")

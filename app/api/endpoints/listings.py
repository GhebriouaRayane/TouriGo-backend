from typing import Any, List, Optional
from pathlib import Path
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.api import deps
from app.db.session import get_db
from app.models.models import Listing, ListingImage, ListingType, User, UserRole
from app.schemas.schemas import ListingCreate, ListingOut, ListingUpdate, MessageResponse

router = APIRouter()

LISTINGS_MEDIA_DIR = Path(__file__).resolve().parents[3] / "media" / "listings"
FALLBACK_IMAGE_BY_TYPE: dict[str, str] = {
    "immobilier": "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=800",
    "vehicule": "https://images.unsplash.com/photo-1614200179396-2bdb77ebf81b?w=800",
    "activite": "https://images.unsplash.com/photo-1654127655303-b955c3763777?w=800",
}


def _sanitize_listing_images(listing: Listing) -> None:
    listing_type = (listing.type or "").strip().lower()
    fallback = FALLBACK_IMAGE_BY_TYPE.get(listing_type, FALLBACK_IMAGE_BY_TYPE["immobilier"])
    for image in listing.images:
        raw_url = (image.url or "").strip()
        if not raw_url:
            image.url = fallback
            continue
        parsed = urlparse(raw_url)
        image_path = parsed.path or raw_url
        if "/media/listings/" not in image_path:
            continue
        filename = Path(image_path).name
        if not filename:
            image.url = fallback
            continue
        if not (LISTINGS_MEDIA_DIR / filename).is_file():
            image.url = fallback


def _sanitize_listings_images(listings: list[Listing]) -> None:
    for listing in listings:
        _sanitize_listing_images(listing)


def _ensure_listing_management_permission(current_user: User, listing: Listing) -> None:
    if current_user.role == UserRole.ADMIN.value:
        return
    if current_user.role != UserRole.HOST.value:
        raise HTTPException(status_code=403, detail="Seuls les hotes peuvent modifier des annonces.")
    if listing.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Vous ne pouvez modifier que vos propres annonces.")


def _get_listing_by_id(db: Session, listing_id: int) -> Listing:
    listing = (
        db.query(Listing)
        .options(joinedload(Listing.images), joinedload(Listing.owner))
        .filter(Listing.id == listing_id)
        .first()
    )
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    _sanitize_listing_images(listing)
    return listing


@router.get("/", response_model=List[ListingOut])
def read_listings(
    db: Session = Depends(get_db),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    type: Optional[ListingType] = None,
    category: Optional[str] = None,
    location: Optional[str] = None,
) -> Any:
    """
    Retrieve listings.
    """
    query = db.query(Listing).options(joinedload(Listing.images), joinedload(Listing.owner))
    if type:
        query = query.filter(Listing.type == type.value)
    if category:
        query = query.filter(func.lower(Listing.category) == category.strip().lower())
    if location:
        query = query.filter(Listing.location.contains(location))
    
    listings = query.offset(skip).limit(limit).all()
    _sanitize_listings_images(listings)
    return listings

@router.get("/me", response_model=List[ListingOut])
def read_my_listings(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Retrieve listings created by the authenticated user.
    """
    listings = (
        db.query(Listing)
        .options(joinedload(Listing.images), joinedload(Listing.owner))
        .filter(Listing.owner_id == current_user.id)
        .all()
    )
    _sanitize_listings_images(listings)
    return listings

@router.post(
    "/",
    response_model=ListingOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"description": "Forbidden"},
    },
)
def create_listing(
    *,
    db: Session = Depends(get_db),
    listing_in: ListingCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Create new listing.
    """
    if current_user.role not in {UserRole.HOST.value, UserRole.ADMIN.value}:
        raise HTTPException(status_code=403, detail="Seuls les hotes peuvent publier des annonces.")

    payload = listing_in.model_dump(mode="json")
    image_urls = payload.pop("image_urls", [])
    listing = Listing(
        **payload,
        owner_id=current_user.id
    )
    db.add(listing)
    db.flush()
    for url in image_urls:
        db.add(ListingImage(url=url, listing_id=listing.id))
    db.commit()
    return _get_listing_by_id(db, listing.id)

@router.get("/{id}", response_model=ListingOut)
def read_listing(
    *,
    db: Session = Depends(get_db),
    id: int,
) -> Any:
    """
    Get listing by ID.
    """
    return _get_listing_by_id(db, id)


@router.patch("/{id}", response_model=ListingOut)
def update_listing(
    *,
    db: Session = Depends(get_db),
    id: int,
    listing_in: ListingUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Update an existing listing owned by the current host.
    """
    listing = _get_listing_by_id(db, id)
    _ensure_listing_management_permission(current_user, listing)

    update_data = listing_in.model_dump(mode="json", exclude_unset=True)
    image_urls = update_data.pop("image_urls", None)

    merged_payload = {
        "title": update_data.get("title", listing.title),
        "description": update_data.get("description", listing.description),
        "type": update_data.get("type", listing.type),
        "category": update_data.get("category", listing.category),
        "location": update_data.get("location", listing.location),
        "price": update_data.get("price", listing.price),
        "period": update_data.get("period", listing.period),
        "bedrooms": update_data.get("bedrooms", listing.bedrooms),
        "bathrooms": update_data.get("bathrooms", listing.bathrooms),
        "area": update_data.get("area", listing.area),
        "details": update_data.get("details", listing.details),
        "availability_dates": update_data.get("availability_dates", listing.availability_dates),
        "image_urls": image_urls if image_urls is not None else [image.url for image in listing.images],
    }
    merged_type = str(merged_payload["type"])
    if merged_type == ListingType.IMMOBILIER.value:
        merged_category = str(merged_payload["category"] or "").strip().lower()
        is_hotel_category = merged_category in {"hotel", "hôtel"}
        if (
            merged_payload["bedrooms"] is None
            or merged_payload["bathrooms"] is None
            or (not is_hotel_category and merged_payload["area"] is None)
        ):
            raise HTTPException(
                status_code=400,
                detail="Pour une annonce immobilier, chambres et salles de bain sont obligatoires. La surface est obligatoire sauf pour hotel.",
            )
    elif update_data.get("type") in {ListingType.VEHICULE.value, ListingType.ACTIVITE.value} and not (
        merged_payload["details"] and str(merged_payload["details"]).strip()
    ):
        raise HTTPException(
            status_code=400,
            detail="Le champ details est obligatoire pour les annonces vehicule et activite.",
        )

    for field, value in update_data.items():
        setattr(listing, field, value)

    if image_urls is not None:
        listing.images.clear()
        db.flush()
        for url in image_urls:
            db.add(ListingImage(url=url, listing_id=listing.id))

    db.add(listing)
    db.commit()
    return _get_listing_by_id(db, id)


@router.delete(
    "/{id}",
    response_model=MessageResponse,
    responses={
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
    },
)
def delete_listing(
    *,
    db: Session = Depends(get_db),
    id: int,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Delete an existing listing owned by the current host.
    """
    listing = _get_listing_by_id(db, id)
    _ensure_listing_management_permission(current_user, listing)

    db.delete(listing)
    db.commit()
    return {"message": "Annonce supprimee."}

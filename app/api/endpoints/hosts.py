from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.models import Listing, Review, User
from app.schemas.schemas import HostProfileOut

router = APIRouter()


@router.get("/{user_id}", response_model=HostProfileOut)
def read_host_profile(
    *,
    db: Session = Depends(get_db),
    user_id: int,
) -> Any:
    """
    Retrieve a public host profile with their listings and review summary.
    """
    user = (
        db.query(User)
        .options(
            selectinload(User.listings).selectinload(Listing.images),
            selectinload(User.listings).selectinload(Listing.reviews),
        )
        .filter(User.id == user_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="Profil hote introuvable.")

    rating_average, rating_count = (
        db.query(func.avg(Review.rating), func.count(Review.id))
        .select_from(Review)
        .join(Listing, Review.listing_id == Listing.id)
        .filter(Listing.owner_id == user_id)
        .one()
    )

    listings = sorted(user.listings, key=lambda listing: listing.id, reverse=True)

    return HostProfileOut(
        id=user.id,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        phone_number=user.phone_number,
        role=user.role,
        rating_average=float(rating_average) if rating_average is not None else None,
        rating_count=int(rating_count or 0),
        listings=listings,
    )

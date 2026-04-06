from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.api import deps
from app.db.session import get_db
from app.models.models import Listing, Review, User
from app.schemas.schemas import ReviewCreate, ReviewOut

router = APIRouter()


def _get_listing_or_404(db: Session, listing_id: int) -> Listing:
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Annonce introuvable.")
    return listing


def _get_review_with_user_or_404(db: Session, review_id: int) -> Review:
    review = (
        db.query(Review)
        .options(joinedload(Review.user))
        .filter(Review.id == review_id)
        .first()
    )
    if not review:
        raise HTTPException(status_code=404, detail="Avis introuvable.")
    return review


@router.get("/listings/{listing_id}", response_model=List[ReviewOut])
def read_listing_reviews(
    *,
    db: Session = Depends(get_db),
    listing_id: int,
) -> Any:
    _get_listing_or_404(db, listing_id)
    return (
        db.query(Review)
        .options(joinedload(Review.user))
        .filter(Review.listing_id == listing_id)
        .order_by(Review.created_at.desc())
        .all()
    )


@router.post("/", response_model=ReviewOut)
def create_or_update_review(
    *,
    db: Session = Depends(get_db),
    review_in: ReviewCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    listing = _get_listing_or_404(db, review_in.listing_id)
    if listing.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas laisser un avis sur votre propre annonce.")

    normalized_comment = review_in.comment.strip() if review_in.comment else None
    if normalized_comment == "":
        normalized_comment = None

    existing_review = (
        db.query(Review)
        .filter(
            Review.user_id == current_user.id,
            Review.listing_id == review_in.listing_id,
        )
        .first()
    )

    if existing_review:
        existing_review.rating = review_in.rating
        existing_review.comment = normalized_comment
        db.add(existing_review)
        db.commit()
        return _get_review_with_user_or_404(db, existing_review.id)

    review = Review(
        user_id=current_user.id,
        listing_id=review_in.listing_id,
        rating=review_in.rating,
        comment=normalized_comment,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return _get_review_with_user_or_404(db, review.id)

from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import get_db
from app.models.models import Favorite, Listing, User
from app.schemas.schemas import FavoriteOut, ListingOut, MessageResponse

router = APIRouter()


@router.get("/ids", response_model=List[int])
def read_my_favorite_ids(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    favorites = db.query(Favorite).filter(Favorite.user_id == current_user.id).all()
    return [favorite.listing_id for favorite in favorites]


@router.get("/me", response_model=List[ListingOut])
def read_my_favorites(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    favorites = db.query(Favorite).filter(Favorite.user_id == current_user.id).all()
    listing_ids = [favorite.listing_id for favorite in favorites]
    if not listing_ids:
        return []
    return db.query(Listing).filter(Listing.id.in_(listing_ids)).all()


@router.post(
    "/{listing_id}",
    response_model=FavoriteOut,
    responses={
        404: {"description": "Not Found"},
    },
)
def add_favorite(
    *,
    db: Session = Depends(get_db),
    listing_id: int,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Annonce introuvable.")

    favorite = (
        db.query(Favorite)
        .filter(Favorite.user_id == current_user.id, Favorite.listing_id == listing_id)
        .first()
    )
    if favorite:
        return favorite

    favorite = Favorite(user_id=current_user.id, listing_id=listing_id)
    db.add(favorite)
    db.commit()
    db.refresh(favorite)
    return favorite


@router.delete(
    "/{listing_id}",
    response_model=MessageResponse,
    responses={
        404: {"description": "Not Found"},
    },
)
def remove_favorite(
    *,
    db: Session = Depends(get_db),
    listing_id: int,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    favorite = (
        db.query(Favorite)
        .filter(Favorite.user_id == current_user.id, Favorite.listing_id == listing_id)
        .first()
    )
    if not favorite:
        raise HTTPException(status_code=404, detail="Favori introuvable.")

    db.delete(favorite)
    db.commit()
    return {"message": "Favori supprime."}

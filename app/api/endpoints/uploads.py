from pathlib import Path
from uuid import uuid4
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from app.api import deps
from app.models.models import User, UserRole
from app.schemas.schemas import UploadAvatarResponse, UploadListingImagesResponse

router = APIRouter()

MEDIA_DIR = Path(__file__).resolve().parents[3] / "media"
AVATARS_DIR = MEDIA_DIR / "avatars"
LISTINGS_DIR = MEDIA_DIR / "listings"


def _save_image(upload_file: UploadFile, destination_dir: Path) -> str:
    content_type = upload_file.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Seules les images sont autorisees.")

    destination_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(upload_file.filename or "").suffix.lower() or ".jpg"
    filename = f"{uuid4().hex}{suffix}"
    destination = destination_dir / filename
    with destination.open("wb") as file_out:
        file_out.write(upload_file.file.read())
    return filename


@router.post(
    "/avatar",
    response_model=UploadAvatarResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Bad Request"},
    },
)
def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    filename = _save_image(file, AVATARS_DIR)
    url = str(request.url_for("media", path=f"avatars/{filename}"))
    return {"url": url}


@router.post(
    "/listing-images",
    response_model=UploadListingImagesResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Bad Request"},
        403: {"description": "Forbidden"},
    },
)
def upload_listing_images(
    request: Request,
    files: list[UploadFile] = File(...),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    if current_user.role not in {UserRole.HOST.value, UserRole.ADMIN.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Seuls les hotes peuvent ajouter des photos d'annonce.")
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Aucune image fournie.")

    urls: list[str] = []
    for upload_file in files:
        filename = _save_image(upload_file, LISTINGS_DIR)
        urls.append(str(request.url_for("media", path=f"listings/{filename}")))
    return {"urls": urls}

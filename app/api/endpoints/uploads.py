from pathlib import Path
from uuid import uuid4
from typing import Any
from urllib.parse import quote

import requests

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from app.api import deps
from app.core.config import settings
from app.models.models import User, UserRole
from app.schemas.schemas import UploadAvatarResponse, UploadListingImagesResponse

router = APIRouter()

MEDIA_DIR = Path(__file__).resolve().parents[3] / "media"
AVATARS_DIR = MEDIA_DIR / "avatars"
LISTINGS_DIR = MEDIA_DIR / "listings"


def _supabase_storage_enabled() -> bool:
    has_any = any(
        (
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_ROLE_KEY,
            settings.SUPABASE_STORAGE_BUCKET,
        )
    )
    if has_any and not (
        settings.SUPABASE_URL
        and settings.SUPABASE_SERVICE_ROLE_KEY
        and settings.SUPABASE_STORAGE_BUCKET
    ):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Configuration Supabase Storage incomplete.",
        )
    return bool(
        settings.SUPABASE_URL
        and settings.SUPABASE_SERVICE_ROLE_KEY
        and settings.SUPABASE_STORAGE_BUCKET
    )


def _upload_to_supabase(*, file_bytes: bytes, content_type: str, object_path: str) -> str:
    base_url = (settings.SUPABASE_URL or "").rstrip("/")
    bucket = settings.SUPABASE_STORAGE_BUCKET or ""
    api_key = settings.SUPABASE_SERVICE_ROLE_KEY or ""
    safe_path = quote(object_path, safe="/")
    upload_url = f"{base_url}/storage/v1/object/{bucket}/{safe_path}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "apikey": api_key,
        "Content-Type": content_type,
        "x-upsert": "true",
    }
    try:
        response = requests.post(upload_url, headers=headers, data=file_bytes, timeout=20)
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Impossible d'envoyer l'image vers Supabase.",
        ) from exc
    if response.status_code not in {200, 201, 204}:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Echec de l'upload de l'image vers Supabase.",
        )
    return f"{base_url}/storage/v1/object/public/{bucket}/{safe_path}"


def _store_image(
    upload_file: UploadFile,
    request: Request,
    destination_dir: Path,
    local_prefix: str,
    supabase_prefix: str,
) -> str:
    content_type = upload_file.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Seules les images sont autorisees.")

    suffix = Path(upload_file.filename or "").suffix.lower() or ".jpg"
    filename = f"{uuid4().hex}{suffix}"
    file_bytes = upload_file.file.read()
    if _supabase_storage_enabled():
        object_path = f"{supabase_prefix}/{filename}"
        return _upload_to_supabase(
            file_bytes=file_bytes,
            content_type=content_type,
            object_path=object_path,
        )

    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / filename
    with destination.open("wb") as file_out:
        file_out.write(file_bytes)
    return str(request.url_for("media", path=f"{local_prefix}/{filename}"))


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
    url = _store_image(
        upload_file=file,
        request=request,
        destination_dir=AVATARS_DIR,
        local_prefix="avatars",
        supabase_prefix=settings.SUPABASE_STORAGE_AVATARS_PREFIX,
    )
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
        url = _store_image(
            upload_file=upload_file,
            request=request,
            destination_dir=LISTINGS_DIR,
            local_prefix="listings",
            supabase_prefix=settings.SUPABASE_STORAGE_LISTINGS_PREFIX,
        )
        urls.append(url)
    return {"urls": urls}

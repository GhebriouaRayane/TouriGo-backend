from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import PushDeviceToken

logger = logging.getLogger(__name__)

_firebase_app_initialized = False
_firebase_available: bool | None = None


def _initialize_firebase() -> bool:
    global _firebase_app_initialized, _firebase_available

    if _firebase_app_initialized:
        return True
    if _firebase_available is False:
        return False

    service_account_json = settings.FIREBASE_SERVICE_ACCOUNT_JSON
    service_account_file = settings.FIREBASE_SERVICE_ACCOUNT_FILE
    if not service_account_json and not service_account_file:
        _firebase_available = False
        return False

    try:
        import firebase_admin
        from firebase_admin import credentials
    except ImportError:
        logger.warning(
            "firebase-admin n'est pas installe. Ajoutez-le aux dependances backend pour activer les push FCM."
        )
        _firebase_available = False
        return False

    if firebase_admin._apps:
        _firebase_app_initialized = True
        _firebase_available = True
        return True

    try:
        if service_account_json:
            credential = credentials.Certificate(json.loads(service_account_json))
        else:
            credential = credentials.Certificate(str(Path(service_account_file or "").expanduser()))
        firebase_admin.initialize_app(
            credential,
            {"projectId": settings.FIREBASE_PROJECT_ID} if settings.FIREBASE_PROJECT_ID else None,
        )
        _firebase_app_initialized = True
        _firebase_available = True
        return True
    except Exception:
        logger.exception("Impossible d'initialiser Firebase Admin.")
        _firebase_available = False
        return False


def send_push_notification_to_user(
    db: Session,
    *,
    user_id: int,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> int:
    if not _initialize_firebase():
        return 0

    try:
        from firebase_admin import messaging
    except ImportError:
        return 0

    tokens = (
        db.query(PushDeviceToken)
        .filter(PushDeviceToken.user_id == user_id, PushDeviceToken.is_active.is_(True))
        .all()
    )
    if not tokens:
        return 0

    payload_data = {key: str(value) for key, value in (data or {}).items() if value is not None}
    messages = [
        messaging.Message(
            token=device_token.token,
            notification=messaging.Notification(title=title, body=body),
            data=payload_data,
        )
        for device_token in tokens
    ]

    sent_count = 0
    invalid_token_ids: list[int] = []

    for device_token, message in zip(tokens, messages):
        try:
            messaging.send(message)
            sent_count += 1
        except Exception as exc:
            error_code = getattr(exc, "code", "") or exc.__class__.__name__
            normalized_error = str(error_code).lower()
            if "notregistered" in normalized_error or "unregistered" in normalized_error:
                invalid_token_ids.append(device_token.id)
            logger.warning("Echec envoi push pour user_id=%s token_id=%s: %s", user_id, device_token.id, exc)

    if invalid_token_ids:
        (
            db.query(PushDeviceToken)
            .filter(PushDeviceToken.id.in_(invalid_token_ids))
            .update({PushDeviceToken.is_active: False}, synchronize_session=False)
        )
        db.commit()

    return sent_count

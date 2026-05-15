from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import get_db
from app.models.models import PushDeviceToken, User
from app.schemas.schemas import PushTokenDeletePayload, PushTokenOut, PushTokenRegister

router = APIRouter()


@router.post("/register", response_model=PushTokenOut)
def register_push_token(
    *,
    db: Session = Depends(get_db),
    payload: PushTokenRegister,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    push_token = (
        db.query(PushDeviceToken)
        .filter(PushDeviceToken.token == payload.token)
        .first()
    )
    if push_token is None:
        push_token = PushDeviceToken(
            user_id=current_user.id,
            token=payload.token,
            platform=payload.platform.value,
            device_id=payload.device_id,
            is_active=True,
            last_seen_at=datetime.now(timezone.utc),
        )
        db.add(push_token)
    else:
        push_token.user_id = current_user.id
        push_token.platform = payload.platform.value
        push_token.device_id = payload.device_id
        push_token.is_active = True
        push_token.last_seen_at = datetime.now(timezone.utc)
        db.add(push_token)

    db.commit()
    db.refresh(push_token)
    return push_token


@router.delete("/unregister")
def unregister_push_token(
    *,
    db: Session = Depends(get_db),
    payload: PushTokenDeletePayload,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    (
        db.query(PushDeviceToken)
        .filter(
            PushDeviceToken.user_id == current_user.id,
            PushDeviceToken.token == payload.token,
        )
        .update({PushDeviceToken.is_active: False}, synchronize_session=False)
    )
    db.commit()
    return {"message": "Token push desactive."}

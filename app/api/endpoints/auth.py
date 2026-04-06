import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.api import deps
from app.db.session import get_db
from app.models.models import RegistrationCode, User, UserRole, VerificationChannel
from app.schemas.schemas import (
    GoogleLoginRequest,
    MessageResponse,
    RegisterCodeRequest,
    RegisterCodeRequestOut,
    RegisterCodeVerify,
    Token,
    UserDelete,
    UserOut,
    UserPasswordUpdate,
    UserUpdate,
)
from app.services.google_auth import GoogleTokenError, verify_google_id_token
from app.services.registration import generate_numeric_code, mask_target, send_verification_code

router = APIRouter()
PHONE_EMAIL_DOMAIN = "phone.tourigo.local"


def _should_expose_debug_code() -> bool:
    return settings.AUTH_EXPOSE_DEBUG_CODE or settings.ENVIRONMENT != "production"


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _issue_access_token(email: str) -> dict[str, str]:
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": security.create_access_token(
            email, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }


def _normalize_phone_number(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    normalized = re.sub(r"[^\d+]", "", stripped)
    if normalized.startswith("00"):
        normalized = f"+{normalized[2:]}"
    if normalized.count("+") > 1 or ("+" in normalized and not normalized.startswith("+")):
        return None
    digits = normalized[1:] if normalized.startswith("+") else normalized
    if len(digits) < 6:
        return None
    if normalized.startswith("+"):
        return f"+{digits}"
    return digits


def _resolve_account_email(
    *,
    email: str | None,
    phone_number: str | None,
    channel: VerificationChannel,
) -> str:
    if email:
        return email.strip().lower()
    if channel == VerificationChannel.PHONE and phone_number:
        digest = hashlib.sha256(phone_number.encode("utf-8")).hexdigest()[:24]
        return f"phone-{digest}@{PHONE_EMAIL_DOMAIN}"
    raise HTTPException(status_code=400, detail="Identifiant d'inscription invalide.")

@router.post("/login/access-token", response_model=Token)
def login_access_token(
    db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    identifier = form_data.username.strip()
    if not identifier:
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    filters = [func.lower(User.email) == identifier.lower()]
    normalized_phone = _normalize_phone_number(identifier)
    if normalized_phone:
        filters.append(User.phone_number == normalized_phone)
    user = db.query(User).filter(or_(*filters)).first()
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return _issue_access_token(user.email)


@router.post("/login/google", response_model=Token)
def login_google(
    *,
    db: Session = Depends(get_db),
    payload: GoogleLoginRequest,
) -> Any:
    """
    Authenticate a user with a Google id_token.
    """
    try:
        google_claims = verify_google_id_token(payload.id_token, settings.GOOGLE_CLIENT_ID or "")
    except GoogleTokenError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    email = str(google_claims["email"]).strip().lower()
    user = db.query(User).filter(func.lower(User.email) == email).first()
    if not user:
        user = User(
            email=email,
            hashed_password=security.get_password_hash(secrets.token_urlsafe(32)),
            full_name=google_claims.get("name"),
            avatar_url=google_claims.get("picture"),
            role=UserRole.USER.value,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        changed = False
        if not user.full_name and isinstance(google_claims.get("name"), str):
            user.full_name = google_claims["name"]
            changed = True
        if not user.avatar_url and isinstance(google_claims.get("picture"), str):
            user.avatar_url = google_claims["picture"]
            changed = True
        if changed:
            db.add(user)
            db.commit()

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    return _issue_access_token(user.email)

@router.post("/register", response_model=RegisterCodeRequestOut)
def register_user(
    *,
    db: Session = Depends(get_db),
    user_in: RegisterCodeRequest,
) -> Any:
    """
    Start registration by sending a verification code.
    """
    normalized_phone = _normalize_phone_number(user_in.phone_number)
    if user_in.phone_number and not normalized_phone:
        raise HTTPException(status_code=400, detail="Numero de telephone invalide.")
    if user_in.channel == VerificationChannel.PHONE and not normalized_phone:
        raise HTTPException(status_code=400, detail="Numero de telephone invalide.")

    account_email = _resolve_account_email(
        email=user_in.email,
        phone_number=normalized_phone,
        channel=user_in.channel,
    )
    existing_filters = [func.lower(User.email) == account_email]
    if normalized_phone:
        existing_filters.append(User.phone_number == normalized_phone)
    existing_user = db.query(User).filter(or_(*existing_filters)).first()
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Un compte existe deja avec cet email ou ce numero.",
        )

    now = datetime.now(timezone.utc)
    db.query(RegistrationCode).filter(
        RegistrationCode.email == account_email,
        RegistrationCode.consumed_at.is_(None),
    ).delete(synchronize_session=False)

    verification_code = generate_numeric_code(settings.REGISTRATION_CODE_LENGTH)
    role = UserRole.HOST.value if user_in.become_host else UserRole.USER.value
    verification = RegistrationCode(
        email=account_email,
        phone_number=normalized_phone,
        full_name=user_in.full_name,
        avatar_url=user_in.avatar_url,
        hashed_password=security.get_password_hash(user_in.password),
        role=role,
        channel=user_in.channel.value,
        hashed_code=security.get_password_hash(verification_code),
        expires_at=now + timedelta(minutes=settings.REGISTRATION_CODE_EXPIRE_MINUTES),
    )
    db.add(verification)
    db.commit()
    db.refresh(verification)

    target = user_in.email if user_in.channel == VerificationChannel.EMAIL else normalized_phone
    if target is None:
        raise HTTPException(status_code=400, detail="Cible de verification invalide.")

    delivery_ok = send_verification_code(user_in.channel, target, verification_code)
    debug_code = verification_code if _should_expose_debug_code() else None
    if not delivery_ok and debug_code is None:
        db.delete(verification)
        db.commit()
        raise HTTPException(
            status_code=503,
            detail=(
                "Impossible d'envoyer le code de verification. "
                "Configurez SMTP pour email ou SMS_WEBHOOK_URL pour telephone."
            ),
        )

    message = "Code de verification envoye."
    if not delivery_ok and debug_code is not None:
        message = "Canal non configure: code de verification retourne en mode developpement."

    return {
        "verification_id": verification.id,
        "message": message,
        "channel": user_in.channel,
        "target": mask_target(user_in.channel, target),
        "expires_at": verification.expires_at,
        "debug_code": debug_code,
    }


@router.post(
    "/register/verify-code",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Bad Request"},
    },
)
def verify_registration_code(
    *,
    db: Session = Depends(get_db),
    payload: RegisterCodeVerify,
) -> Any:
    """
    Finalize registration after OTP validation.
    """
    verification = db.query(RegistrationCode).filter(RegistrationCode.id == payload.verification_id).first()
    if not verification or verification.consumed_at is not None:
        raise HTTPException(status_code=400, detail="Demande d'inscription invalide ou deja utilisee.")

    if _as_utc(verification.expires_at) < datetime.now(timezone.utc):
        db.delete(verification)
        db.commit()
        raise HTTPException(status_code=400, detail="Le code a expire. Demandez un nouveau code.")

    if verification.attempts >= settings.REGISTRATION_CODE_MAX_ATTEMPTS:
        db.delete(verification)
        db.commit()
        raise HTTPException(status_code=400, detail="Nombre maximum de tentatives atteint.")

    if not security.verify_password(payload.code, verification.hashed_code):
        verification.attempts += 1
        remaining_attempts = settings.REGISTRATION_CODE_MAX_ATTEMPTS - verification.attempts
        if remaining_attempts <= 0:
            db.delete(verification)
            db.commit()
            raise HTTPException(status_code=400, detail="Code incorrect. Demande expiree, recommencez l'inscription.")
        db.add(verification)
        db.commit()
        raise HTTPException(
            status_code=400,
            detail=f"Code incorrect. Tentatives restantes: {remaining_attempts}.",
        )

    existing_filters = [func.lower(User.email) == verification.email.lower()]
    if verification.phone_number:
        existing_filters.append(User.phone_number == verification.phone_number)
    existing_user = db.query(User).filter(or_(*existing_filters)).first()
    if existing_user:
        db.delete(verification)
        db.commit()
        raise HTTPException(status_code=400, detail="Ce compte existe deja.")

    user_obj = User(
        email=verification.email,
        hashed_password=verification.hashed_password,
        full_name=verification.full_name,
        avatar_url=verification.avatar_url,
        phone_number=verification.phone_number,
        role=verification.role,
    )
    verification.consumed_at = datetime.now(timezone.utc)
    db.add(user_obj)
    db.add(verification)
    db.commit()
    db.refresh(user_obj)
    return user_obj

@router.get("/me", response_model=UserOut)
def read_current_user(
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get current authenticated user profile.
    """
    return current_user


@router.post("/become-host", response_model=UserOut)
def become_host(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Promote the authenticated user to host role.
    """
    if current_user.role != UserRole.HOST.value:
        current_user.role = UserRole.HOST.value
        db.add(current_user)
        db.commit()
        db.refresh(current_user)
    return current_user


@router.patch("/me", response_model=UserOut)
def update_current_user(
    *,
    db: Session = Depends(get_db),
    user_in: UserUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Update current authenticated user profile.
    """
    update_data = user_in.model_dump(exclude_unset=True)
    new_email = update_data.get("email")
    if new_email and new_email != current_user.email:
        existing = db.query(User).filter(User.email == new_email).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cet email est deja utilise.")
    for field, value in update_data.items():
        setattr(current_user, field, value)
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.delete("/me", response_model=MessageResponse)
def delete_current_user(
    *,
    db: Session = Depends(get_db),
    payload: UserDelete,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Delete current authenticated user account.
    """
    if not security.verify_password(payload.password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mot de passe actuel incorrect.")
    db.delete(current_user)
    db.commit()
    return {"message": "Compte supprime avec succes."}


@router.post(
    "/change-password",
    response_model=MessageResponse,
    responses={
        400: {"description": "Bad Request"},
    },
)
def change_password(
    *,
    db: Session = Depends(get_db),
    payload: UserPasswordUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Change current authenticated user password.
    """
    if not security.verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mot de passe actuel incorrect.")
    current_user.hashed_password = security.get_password_hash(payload.new_password)
    db.add(current_user)
    db.commit()
    return {"message": "Mot de passe modifie avec succes."}

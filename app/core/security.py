from datetime import datetime, timedelta, timezone
import hashlib
from typing import Any
import bcrypt
from jose import jwt
from app.core.config import settings

ALGORITHM = "HS256"

def _bcrypt_input(password: str) -> bytes:
    """
    bcrypt only supports 72 bytes. We pre-hash long inputs to keep behavior stable.
    """
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        return hashlib.sha256(password_bytes).hexdigest().encode("utf-8")
    return password_bytes

def create_access_token(subject: str | Any, expires_delta: timedelta | None = None) -> str:
    if expires_delta is not None:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            _bcrypt_input(plain_password),
            hashed_password.encode("utf-8"),
        )
    except ValueError:
        return False

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(_bcrypt_input(password), bcrypt.gensalt()).decode("utf-8")

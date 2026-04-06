from __future__ import annotations
import json
import logging
import secrets
from urllib import request as urllib_request
from urllib.error import URLError, HTTPError
from app.core.config import settings
from app.models.models import VerificationChannel
logger = logging.getLogger(__name__)

def generate_numeric_code(length: int) -> str:
    if length < 4:
        raise ValueError("La longueur du code OTP doit etre au moins 4.")
    return f"{secrets.randbelow(10 ** length):0{length}d}"

def mask_target(channel: VerificationChannel, target: str) -> str:
    if channel == VerificationChannel.EMAIL:
        local, sep, domain = target.partition("@")
        if not sep:
            return "***"
        if len(local) <= 2:
            masked_local = f"{local[:1]}*"
        else:
            masked_local = f"{local[:2]}{'*' * (len(local) - 2)}"
        return f"{masked_local}@{domain}"
    digits_only = "".join(ch for ch in target if ch.isdigit())
    if len(digits_only) <= 2:
        return f"{'*' * max(len(digits_only), 1)}"
    return f"{'*' * (len(digits_only) - 2)}{digits_only[-2:]}"

def send_verification_code(channel: VerificationChannel, target: str, code: str) -> bool:
    if channel == VerificationChannel.EMAIL:
        return _send_email_code(target=target, code=code)
    return _send_sms_code(target=target, code=code)

def _send_email_code(*, target: str, code: str) -> bool:
    if not settings.RESEND_API_KEY:
        logger.warning("Resend non configure: impossible d'envoyer le code par email.")
        return False
    payload = json.dumps({
        "from": "TouriGo <rayaneghebrioua10@gmail.com>",
        "to": [target],
        "subject": "Code de confirmation TouriGo",
        "text": (
            f"Votre code de confirmation TouriGo est: {code}\n"
            f"Ce code expire dans {settings.REGISTRATION_CODE_EXPIRE_MINUTES} minutes."
        ),
    }).encode("utf-8")
    req = urllib_request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {settings.RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=10) as response:
            return 200 <= response.status < 300
    except Exception as exc:
        logger.exception("Echec envoi email OTP via Resend: %s", exc)
        return False

def _send_sms_code(*, target: str, code: str) -> bool:
    if not settings.SMS_WEBHOOK_URL:
        logger.warning("SMS webhook non configure: impossible d'envoyer le code par telephone.")
        return False
    payload = json.dumps({
        "phone_number": target,
        "message": (
            f"Votre code TouriGo est {code}. "
            f"Expiration dans {settings.REGISTRATION_CODE_EXPIRE_MINUTES} minutes."
        ),
        "code": code,
    }).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if settings.SMS_WEBHOOK_TOKEN:
        headers["Authorization"] = f"Bearer {settings.SMS_WEBHOOK_TOKEN}"
    req = urllib_request.Request(
        settings.SMS_WEBHOOK_URL,
        data=payload,
        headers=headers,
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=10) as response:
            status_code = getattr(response, "status", None) or response.getcode()
            return 200 <= int(status_code) < 300
    except (URLError, HTTPError) as exc:
        logger.exception("Echec envoi SMS OTP: %s", exc)
        return False

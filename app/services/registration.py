from __future__ import annotations

import json
import logging
import secrets
import smtplib
from email.message import EmailMessage
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
    if not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
        logger.warning("SMTP non configure: impossible d'envoyer le code par email.")
        return False

    message = EmailMessage()
    message["Subject"] = "Code de confirmation TouriGo"
    message["From"] = settings.SMTP_FROM_EMAIL
    message["To"] = target
    message.set_content(
        f"Votre code de confirmation TouriGo est: {code}\n"
        f"Ce code expire dans {settings.REGISTRATION_CODE_EXPIRE_MINUTES} minutes."
    )

    try:
        if settings.SMTP_USE_SSL:
            smtp_client: smtplib.SMTP = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
        else:
            smtp_client = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
        with smtp_client as server:
            if settings.SMTP_USE_TLS and not settings.SMTP_USE_SSL:
                server.starttls()
            if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(message)
        return True
    except Exception as exc:
        logger.exception("Echec envoi email OTP: %s", exc)
        return False


def _send_sms_code(*, target: str, code: str) -> bool:
    if not settings.SMS_WEBHOOK_URL:
        logger.warning("SMS webhook non configure: impossible d'envoyer le code par telephone.")
        return False

    payload = json.dumps(
        {
            "phone_number": target,
            "message": (
                f"Votre code TouriGo est {code}. "
                f"Expiration dans {settings.REGISTRATION_CODE_EXPIRE_MINUTES} minutes."
            ),
            "code": code,
        }
    ).encode("utf-8")

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

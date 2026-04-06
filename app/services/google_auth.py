from __future__ import annotations

import json
import re
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from jose import jwk, jwt
from jose.utils import base64url_decode

GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}

_JWKS_CACHE: dict[str, Any] = {
    "keys": None,
    "expires_at": 0.0,
}


class GoogleTokenError(ValueError):
    pass


def _extract_max_age(cache_control_header: str | None) -> int:
    if not cache_control_header:
        return 300
    match = re.search(r"max-age=(\d+)", cache_control_header)
    if not match:
        return 300
    return max(60, int(match.group(1)))


def _fetch_google_jwks(force_refresh: bool = False) -> list[dict[str, Any]]:
    now = time.time()
    cached_keys = _JWKS_CACHE.get("keys")
    cached_expiration = float(_JWKS_CACHE.get("expires_at", 0))

    if not force_refresh and isinstance(cached_keys, list) and now < cached_expiration:
        return cached_keys

    request = Request(GOOGLE_JWKS_URL, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
            keys = payload.get("keys")
            if not isinstance(keys, list) or not keys:
                raise GoogleTokenError("Reponse Google invalide pendant la verification du token.")
            cache_seconds = _extract_max_age(response.headers.get("Cache-Control"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        if isinstance(cached_keys, list) and cached_keys:
            return cached_keys
        raise GoogleTokenError("Impossible de verifier le token Google pour le moment.") from exc

    _JWKS_CACHE["keys"] = keys
    _JWKS_CACHE["expires_at"] = now + cache_seconds
    return keys


def _get_google_key(kid: str, *, retry: bool = True) -> dict[str, Any]:
    keys = _fetch_google_jwks(force_refresh=not retry)
    for key_data in keys:
        if key_data.get("kid") == kid:
            return key_data
    if retry:
        return _get_google_key(kid, retry=False)
    raise GoogleTokenError("Cle de signature Google introuvable.")


def _verify_token_signature(id_token: str, key_data: dict[str, Any]) -> None:
    try:
        public_key = jwk.construct(key_data, algorithm="RS256")
        signing_input, encoded_signature = id_token.rsplit(".", 1)
        decoded_signature = base64url_decode(encoded_signature.encode("utf-8"))
    except Exception as exc:
        raise GoogleTokenError("Token Google invalide.") from exc

    if not public_key.verify(signing_input.encode("utf-8"), decoded_signature):
        raise GoogleTokenError("Signature du token Google invalide.")


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == "true"
    return False


def _as_int_claim(value: Any, error_message: str) -> int:
    if value is None or isinstance(value, bool):
        raise GoogleTokenError(error_message)
    if not isinstance(value, (int, str)):
        raise GoogleTokenError(error_message)
    try:
        return int(value)
    except ValueError as exc:
        raise GoogleTokenError(error_message) from exc


def _validate_google_claims(claims: dict[str, Any], audience: str) -> None:
    issuer = claims.get("iss")
    if issuer not in GOOGLE_ISSUERS:
        raise GoogleTokenError("Emetteur Google invalide.")

    token_audience = claims.get("aud")
    if token_audience != audience:
        raise GoogleTokenError("Le token Google ne correspond pas a cette application.")

    now = int(time.time())

    exp = _as_int_claim(claims.get("exp"), "Expiration du token Google invalide.")
    if exp <= now:
        raise GoogleTokenError("Le token Google a expire.")

    nbf_raw = claims.get("nbf")
    if nbf_raw is not None:
        nbf = _as_int_claim(nbf_raw, "Le token Google n'est pas encore valide.")
        if nbf > now + 60:
            raise GoogleTokenError("Le token Google n'est pas encore valide.")

    email = claims.get("email")
    if not isinstance(email, str) or not email.strip():
        raise GoogleTokenError("Le token Google ne contient pas d'email.")
    if not _as_bool(claims.get("email_verified")):
        raise GoogleTokenError("L'email Google n'est pas verifie.")

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise GoogleTokenError("Identifiant Google invalide.")


def verify_google_id_token(id_token: str, audience: str) -> dict[str, Any]:
    if not audience:
        raise GoogleTokenError("GOOGLE_CLIENT_ID est manquant cote backend.")

    if not id_token or id_token.count(".") != 2:
        raise GoogleTokenError("Format de token Google invalide.")

    try:
        headers = jwt.get_unverified_header(id_token)
    except Exception as exc:
        raise GoogleTokenError("Entete du token Google invalide.") from exc

    algorithm = headers.get("alg")
    if algorithm != "RS256":
        raise GoogleTokenError("Algorithme du token Google non supporte.")

    kid = headers.get("kid")
    if not isinstance(kid, str) or not kid:
        raise GoogleTokenError("Identifiant de cle Google manquant.")

    key_data = _get_google_key(kid)
    _verify_token_signature(id_token, key_data)

    try:
        claims = jwt.get_unverified_claims(id_token)
    except Exception as exc:
        raise GoogleTokenError("Claims du token Google invalides.") from exc

    _validate_google_claims(claims, audience)
    return claims

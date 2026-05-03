from __future__ import annotations

import hashlib
import hmac
import secrets
import string

from fastapi import Response

from app.config import get_settings

COOKIE_NAME = "warparty_session"
COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 90
REMEMBERED_PLAYER_NAME_COOKIE = "warparty_player_name"
REMEMBERED_PLAYER_NAME_MAX_AGE_SECONDS = 60 * 60 * 24 * 365
_PUBLIC_ALPHABET = string.ascii_lowercase + string.digits
_INVITE_ALPHABET = string.ascii_uppercase + string.digits


def generate_public_id(length: int = 10) -> str:
    return "".join(secrets.choice(_PUBLIC_ALPHABET) for _ in range(length))


def generate_invite_code(length: int = 6) -> str:
    return "".join(secrets.choice(_INVITE_ALPHABET) for _ in range(length))


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_session_token(token: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_session_token(token), expected_hash)


def csrf_token_for_session(player_id: int, token: str, party_id: str) -> str:
    settings = get_settings()
    message = f"{player_id}:{party_id}:{token}".encode()
    return hmac.new(settings.secret_key.encode("utf-8"), message, hashlib.sha256).hexdigest()


def csrf_token_from_cookie(raw_cookie: str | None, party_id: str) -> str | None:
    decoded = decode_session_cookie(raw_cookie)
    if decoded is None:
        return None
    player_id, token = decoded
    return csrf_token_for_session(player_id, token, party_id)


def verify_csrf_token(raw_cookie: str | None, party_id: str, submitted_token: str) -> bool:
    expected_token = csrf_token_from_cookie(raw_cookie, party_id)
    if expected_token is None:
        return False
    return hmac.compare_digest(expected_token, submitted_token)


def encode_session_cookie(player_id: int, token: str) -> str:
    return f"{player_id}:{token}"


def decode_session_cookie(raw_cookie: str | None) -> tuple[int, str] | None:
    if not raw_cookie or ":" not in raw_cookie:
        return None
    raw_player_id, token = raw_cookie.split(":", 1)
    try:
        player_id = int(raw_player_id)
    except ValueError:
        return None
    if not token:
        return None
    return player_id, token


def set_session_cookie(response: Response, player_id: int, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        COOKIE_NAME,
        encode_session_cookie(player_id, token),
        max_age=COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


def set_remembered_player_name_cookie(response: Response, display_name: str) -> None:
    settings = get_settings()
    response.set_cookie(
        REMEMBERED_PLAYER_NAME_COOKIE,
        display_name,
        max_age=REMEMBERED_PLAYER_NAME_MAX_AGE_SECONDS,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )

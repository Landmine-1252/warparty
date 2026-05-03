from __future__ import annotations

import hashlib
import hmac
import secrets
import string

from fastapi import Response

COOKIE_NAME = "warparty_session"
COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 90
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
    response.set_cookie(
        COOKIE_NAME,
        encode_session_cookie(player_id, token),
        max_age=COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=False,
        samesite="lax",
    )

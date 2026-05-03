from __future__ import annotations

from app.config import get_settings
from app.models import Party


def invite_url(party: Party) -> str:
    base_url = get_settings().public_base_url.rstrip("/")
    return f"{base_url}/join/{party.invite_code}"

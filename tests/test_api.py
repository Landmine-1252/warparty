from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.routers.api import get_party_json, get_party_route_json
from app.security import encode_session_cookie
from app.services.parties import create_party
from app.services.warplans import save_warplan


def test_get_party_json_requires_current_player(db_session) -> None:
    party, _, _ = create_party(db_session, "Cipher")

    with pytest.raises(HTTPException) as exc_info:
        get_party_json(party.id, None, db_session)

    assert exc_info.value.status_code == 403


def test_get_party_json_includes_invite_code_for_current_player(db_session) -> None:
    party, player, token = create_party(db_session, "Cipher")

    response = get_party_json(
        party.id,
        encode_session_cookie(player.id, token),
        db_session,
    )

    assert response.invite_code == party.invite_code


def test_get_party_route_json_requires_current_player(db_session) -> None:
    party, player, _ = create_party(db_session, "Cipher")
    save_warplan(db_session, player, ["helltide"])

    with pytest.raises(HTTPException) as exc_info:
        get_party_route_json(party.id, None, db_session)

    assert exc_info.value.status_code == 403

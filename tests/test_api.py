from __future__ import annotations

from app.routers.api import get_party_json
from app.security import encode_session_cookie
from app.services.parties import create_party


def test_get_party_json_hides_invite_code_without_current_player(db_session) -> None:
    party, _, _ = create_party(db_session, "Cipher")

    response = get_party_json(party.id, None, db_session)

    assert response.invite_code is None


def test_get_party_json_includes_invite_code_for_current_player(db_session) -> None:
    party, player, token = create_party(db_session, "Cipher")

    response = get_party_json(
        party.id,
        encode_session_cookie(player.id, token),
        db_session,
    )

    assert response.invite_code == party.invite_code

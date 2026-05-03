from __future__ import annotations

from app.security import encode_session_cookie
from app.services.parties import create_party, join_party
from app.services.players import get_current_player
from app.services.warplans import get_activities, save_warplan


def test_create_party_creates_slot_one_player_and_invite_code(db_session) -> None:
    party, player, token = create_party(db_session, "Cipher")

    assert party.id
    assert party.invite_code
    assert party.leader_player_id == player.id
    assert player.slot_number == 1
    assert token


def test_join_fills_next_open_slot(db_session) -> None:
    party, _, _ = create_party(db_session, "Cipher")
    _, player_two, _ = join_party(db_session, party.invite_code, "Landmine")
    _, player_three, _ = join_party(db_session, party.invite_code, "Shatter")

    assert player_two.slot_number == 2
    assert player_three.slot_number == 3


def test_full_party_rejects_new_player(db_session) -> None:
    import pytest

    from app.services.errors import ServiceError

    party, _, _ = create_party(db_session, "One")
    join_party(db_session, party.invite_code, "Two", max_players=2)

    with pytest.raises(ServiceError):
        join_party(db_session, party.invite_code, "Three", max_players=2)


def test_current_player_can_save_own_warplan(db_session) -> None:
    _, player, _ = create_party(db_session, "Cipher")

    save_warplan(db_session, player, ["helltide", "pit"])

    assert get_activities(player.warplan) == ["helltide", "pit"]


def test_current_player_cannot_modify_another_players_warplan(db_session) -> None:
    party, player_one, token_one = create_party(db_session, "Cipher")
    _, player_two, token_two = join_party(db_session, party.invite_code, "Landmine")

    current_one = get_current_player(
        db_session,
        party.id,
        encode_session_cookie(player_one.id, token_one),
    )
    current_two = get_current_player(
        db_session,
        party.id,
        encode_session_cookie(player_two.id, token_two),
    )
    assert current_one == player_one
    assert current_two == player_two

    save_warplan(db_session, current_two, ["pit"])
    save_warplan(db_session, current_one, ["helltide"])

    assert get_activities(player_one.warplan) == ["helltide"]
    assert get_activities(player_two.warplan) == ["pit"]


def test_get_current_player_rejects_other_party_cookie(db_session) -> None:
    party_one, player_one, token_one = create_party(db_session, "Cipher")
    party_two, _, _ = create_party(db_session, "Landmine")
    cookie = encode_session_cookie(player_one.id, token_one)

    assert get_current_player(db_session, party_one.id, cookie) == player_one
    assert get_current_player(db_session, party_two.id, cookie) is None

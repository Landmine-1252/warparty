from __future__ import annotations

import pytest

from app.security import csrf_token_from_cookie, encode_session_cookie, verify_csrf_token
from app.services.parties import create_party, join_party
from app.services.players import (
    get_current_player,
    get_player,
    leave_party,
    remove_player_from_party,
    transfer_party_leader,
)
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


def test_csrf_token_is_bound_to_session_and_party(db_session) -> None:
    party, player, token = create_party(db_session, "Cipher")
    cookie = encode_session_cookie(player.id, token)
    csrf_token = csrf_token_from_cookie(cookie, party.id)

    assert csrf_token is not None
    assert verify_csrf_token(cookie, party.id, csrf_token)
    assert not verify_csrf_token(cookie, "other-party", csrf_token)
    assert not verify_csrf_token(cookie, party.id, "bad-token")


def test_party_leader_can_remove_member_and_free_slot(db_session) -> None:
    party, leader, _ = create_party(db_session, "Cipher")
    _, removed_player, _ = join_party(db_session, party.invite_code, "Landmine")
    save_warplan(db_session, removed_player, ["pit"])

    remove_player_from_party(db_session, party, leader, removed_player.id)

    assert get_player(db_session, removed_player.id) is None
    _, new_player, _ = join_party(db_session, party.invite_code, "Kaos")
    assert new_player.slot_number == 2


def test_non_leader_cannot_remove_member(db_session) -> None:
    from app.services.errors import ServiceError

    party, leader, _ = create_party(db_session, "Cipher")
    _, member, _ = join_party(db_session, party.invite_code, "Landmine")

    with pytest.raises(ServiceError):
        remove_player_from_party(db_session, party, member, leader.id)


def test_leader_cannot_remove_self(db_session) -> None:
    from app.services.errors import ServiceError

    party, leader, _ = create_party(db_session, "Cipher")

    with pytest.raises(ServiceError):
        remove_player_from_party(db_session, party, leader, leader.id)


def test_non_leader_can_leave_party_and_free_slot(db_session) -> None:
    party, _, _ = create_party(db_session, "Cipher")
    _, leaving_player, _ = join_party(db_session, party.invite_code, "Landmine")

    leave_party(db_session, party, leaving_player)

    assert get_player(db_session, leaving_player.id) is None
    _, new_player, _ = join_party(db_session, party.invite_code, "Kaos")
    assert new_player.slot_number == 2


def test_leader_must_transfer_before_leaving(db_session) -> None:
    from app.services.errors import ServiceError

    party, leader, _ = create_party(db_session, "Cipher")

    with pytest.raises(ServiceError):
        leave_party(db_session, party, leader)


def test_leader_can_transfer_leadership(db_session) -> None:
    party, leader, _ = create_party(db_session, "Cipher")
    _, new_leader, _ = join_party(db_session, party.invite_code, "Landmine")

    transfer_party_leader(db_session, party, leader, new_leader.id)

    assert party.leader_player_id == new_leader.id


def test_non_leader_cannot_transfer_leadership(db_session) -> None:
    from app.services.errors import ServiceError

    party, leader, _ = create_party(db_session, "Cipher")
    _, member, _ = join_party(db_session, party.invite_code, "Landmine")

    with pytest.raises(ServiceError):
        transfer_party_leader(db_session, party, member, leader.id)

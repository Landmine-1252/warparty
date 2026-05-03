from __future__ import annotations

from starlette.requests import Request

from app.main import app
from app.routers.pages import (
    create_party_page,
    healthz,
    index,
    join_by_code,
    join_party_page,
    party_room,
    readyz,
)
from app.security import REMEMBERED_PLAYER_NAME_COOKIE, encode_session_cookie
from app.services.parties import create_party, join_party


def test_home_page_renders() -> None:
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": [], "app": app})

    response = index(request)

    assert response.status_code == 200
    assert b"Coordinate Diablo War Plans" in response.body


def test_home_page_prefills_remembered_player_name() -> None:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"cookie", f"{REMEMBERED_PLAYER_NAME_COOKIE}=Cipher".encode())],
            "app": app,
        }
    )

    response = index(request)

    assert response.status_code == 200
    assert b'value="Cipher"' in response.body


def test_create_party_page_sets_remembered_player_name_cookie(db_session) -> None:
    response = create_party_page("Cipher", db_session)

    assert any(
        key == b"set-cookie" and b"warparty_player_name=Cipher" in value
        for key, value in response.raw_headers
    )


def test_healthz_returns_ok() -> None:
    assert healthz() == {"status": "ok"}


def test_readyz_checks_database(db_session) -> None:
    assert readyz(db_session) == {"status": "ready"}


def test_party_room_renders_open_slots(db_session) -> None:
    party, _, _ = create_party(db_session, "Cipher")
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": f"/party/{party.id}",
            "headers": [],
            "app": app,
        }
    )

    response = party_room(request, party.id, None, db_session)

    assert response.status_code == 200
    assert b"Player War Plans" in response.body
    assert b"Party Room" not in response.body
    assert b"Slot 2" in response.body
    assert b"Open" in response.body


def test_party_room_renders_current_player_warplan_modal(db_session) -> None:
    party, player, token = create_party(db_session, "Cipher")
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": f"/party/{party.id}",
            "headers": [],
            "app": app,
        }
    )

    response = party_room(request, party.id, encode_session_cookie(player.id, token), db_session)

    assert response.status_code == 200
    assert b'id="warplan-modal"' in response.body
    assert b'id="clear-plan-modal"' in response.body
    assert b"Click Activities To Add" in response.body
    assert b"Create Plan" in response.body
    assert b"Add War Plan" not in response.body
    assert b"window.confirm" not in response.body


def test_warplan_modal_uses_visual_picker_order(db_session) -> None:
    party, player, token = create_party(db_session, "Cipher")
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": f"/party/{party.id}",
            "headers": [],
            "app": app,
        }
    )

    response = party_room(request, party.id, encode_session_cookie(player.id, token), db_session)
    body = response.body.decode()

    assert body.index('data-activity-key="helltide"') < body.index(
        'data-activity-key="nightmare_dungeon"'
    )
    assert body.index('data-activity-key="nightmare_dungeon"') < body.index(
        'data-activity-key="lair_boss"'
    )
    assert body.index('data-activity-key="lair_boss"') < body.index(
        'data-activity-key="infernal_hordes"'
    )
    assert body.index('data-activity-key="infernal_hordes"') < body.index('data-activity-key="pit"')
    assert body.index('data-activity-key="pit"') < body.index(
        'data-activity-key="kurast_undercity"'
    )


def test_party_room_renders_leader_remove_player_modal(db_session) -> None:
    party, leader, token = create_party(db_session, "Cipher")
    join_party(db_session, party.invite_code, "Landmine")
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": f"/party/{party.id}",
            "headers": [],
            "app": app,
        }
    )

    response = party_room(request, party.id, encode_session_cookie(leader.id, token), db_session)

    assert response.status_code == 200
    assert b'id="remove-player-modal"' in response.body
    assert b"Remove Player" in response.body
    assert b"data-confirm-remove-player" in response.body


def test_join_page_full_party_explains_retry(db_session) -> None:
    party, _, _ = create_party(db_session, "One")
    join_party(db_session, party.invite_code, "Two")
    join_party(db_session, party.invite_code, "Three")
    join_party(db_session, party.invite_code, "Four")
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": f"/join/{party.invite_code}",
            "headers": [],
            "app": app,
        }
    )

    response = join_by_code(request, party.invite_code, db_session)

    assert response.status_code == 200
    assert b"This Warparty is full" in response.body
    assert b"party leader to remove someone" in response.body
    assert b"Retry Join" in response.body


async def test_join_post_full_party_renders_full_page(db_session) -> None:
    party, _, _ = create_party(db_session, "One")
    join_party(db_session, party.invite_code, "Two")
    join_party(db_session, party.invite_code, "Three")
    join_party(db_session, party.invite_code, "Four")
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/join",
            "headers": [(b"cookie", f"{REMEMBERED_PLAYER_NAME_COOKIE}=Kaos".encode())],
            "app": app,
        }
    )

    response = await join_party_page(request, party.invite_code, "Kaos", db_session)

    assert response.status_code == 409
    assert b"This Warparty is full" in response.body
    assert b'value="Kaos"' in response.body

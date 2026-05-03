from __future__ import annotations

from starlette.requests import Request

from app.main import app
from app.routers.pages import healthz, index, party_room, readyz
from app.security import encode_session_cookie
from app.services.parties import create_party


def test_home_page_renders() -> None:
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": [], "app": app})

    response = index(request)

    assert response.status_code == 200
    assert b"Coordinate Diablo War Plans" in response.body


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

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from starlette.requests import Request

from app.main import app
from app.routers.pages import (
    create_party_page,
    healthz,
    index,
    join_by_code,
    join_party_page,
    my_warplan,
    party_room,
    party_room_live,
    readyz,
    save_my_warplan,
)
from app.security import REMEMBERED_PLAYER_NAME_COOKIE, encode_session_cookie
from app.services.invites import invite_url
from app.services.parties import create_party, join_party
from app.services.players import leave_party, remove_player_from_party
from app.services.warplans import save_warplan


def test_home_page_renders() -> None:
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": [], "app": app})

    response = index(request)

    assert response.status_code == 200
    assert b"Coordinate Diablo War Plans" in response.body
    assert b'class="app-brand-mark brand-mark"' in response.body
    assert b'class="form-field"' in response.body
    assert b'class="action-row form-actions"' in response.body
    assert b"icons/favicon/icon-512.png" in response.body
    assert b"icons/favicon/favicon.ico" in response.body
    assert b"icons/favicon/site.webmanifest" in response.body


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


def test_party_room_requires_current_player(db_session) -> None:
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

    assert response.status_code == 403
    assert b"Private Warparty" in response.body
    assert b"Join this Warparty with a current invite link or invite code" in response.body
    assert b"Player War Plans" not in response.body
    assert b"Recommended Party Route" not in response.body
    assert b"Copy Invite" not in response.body
    assert party.invite_code.encode() not in response.body


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
    assert b"Slot 2" in response.body
    assert b"Open" in response.body
    assert b"Share the invite link." in response.body
    assert b"Choose Activities" in response.body
    assert b"Choose up to 5 activities in order." in response.body
    assert b"Create Plan" in response.body
    assert b'<button class="nav-leave-button" type="submit">Leave</button>' in response.body
    assert b"No War Plan entered." in response.body
    assert b"No Plan" not in response.body
    assert b"0/5 selected" in response.body
    assert b"data-selected-count" in response.body
    assert b"Copy Code" not in response.body
    assert f'data-copy="{party.invite_code}"'.encode() not in response.body
    assert b"data-shortcut-edit-plan" in response.body
    assert b"data-shortcut-copy-invite" in response.body
    assert b"data-shortcut-copy-code" not in response.body
    assert b'href="#icon-x"' in response.body
    assert b'href="#icon-link"' in response.body
    assert b"Add War Plan" not in response.body
    assert b"Open Invite" not in response.body
    assert f'data-copy="{invite_url(party)}"'.encode() in response.body
    assert b"Join my Warparty" not in response.body
    assert b"Invite code:" not in response.body
    assert b"window.confirm" not in response.body
    assert b"window.location.reload" not in response.body
    assert b"liveRefreshIntervalMs = 30000" in response.body
    assert b"setInterval(queuePartyRefresh" in response.body
    assert b"syncWarplanModalFromLiveRegion" in response.body
    assert b"clearInterval" in response.body
    assert b"/live" in response.body


def test_party_room_live_renders_refresh_fragment_without_modal(db_session) -> None:
    party, player, token = create_party(db_session, "Cipher")
    save_warplan(db_session, player, ["helltide", "pit"])
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": f"/party/{party.id}/live",
            "headers": [],
            "app": app,
        }
    )

    response = party_room_live(
        request,
        party.id,
        encode_session_cookie(player.id, token),
        db_session,
    )

    assert response.status_code == 200
    assert b"data-party-live-region" in response.body
    assert b"data-current-player-activities" in response.body
    assert b"helltide" in response.body
    assert b"pit" in response.body
    assert b'data-current-player-progress="0"' in response.body
    assert b"Player War Plans" in response.body
    assert b'id="warplan-modal"' not in response.body
    assert b"<script>" not in response.body


def test_party_room_live_deleted_party_gets_notice_without_full_error_page(db_session) -> None:
    party, player, token = create_party(db_session, "Cipher")
    party_id = party.id
    player_id = player.id
    leave_party(db_session, party, player)
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": f"/party/{party_id}/live",
            "headers": [],
            "app": app,
        }
    )

    response = party_room_live(
        request,
        party_id,
        encode_session_cookie(player_id, token),
        db_session,
    )

    assert response.status_code == 200
    assert b"data-party-access-denied" in response.body
    assert b"Warparty Ended" in response.body
    assert b"data-party-live-region" in response.body
    assert b"Something Went Wrong" not in response.body


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


def test_party_room_renders_leader_remove_for_member_slot(
    db_session,
) -> None:
    party, leader, token = create_party(db_session, "Cipher")
    _, member, _ = join_party(db_session, party.invite_code, "Landmine")
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
    assert b"Make Leader" in response.body
    assert b'id="remove-player-modal"' in response.body
    assert b'class="modal-body"' in response.body
    assert b'class="modal-footer modal-actions"' in response.body
    assert f"/players/{member.id}/remove".encode() in response.body
    assert b'aria-label="Remove Landmine"' in response.body
    assert b"button-icon-danger" in response.body
    assert b'href="#icon-trash"' in response.body


def test_party_room_renders_leader_remove_when_party_is_full(db_session) -> None:
    party, leader, token = create_party(db_session, "Cipher")
    join_party(db_session, party.invite_code, "Landmine")
    join_party(db_session, party.invite_code, "Kaos")
    join_party(db_session, party.invite_code, "Shatter")
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
    assert b"data-confirm-remove-player" in response.body
    assert b'id="transfer-leader-modal"' in response.body


def test_party_room_renders_leader_remove_when_player_is_stale(db_session) -> None:
    party, leader, token = create_party(db_session, "Cipher")
    _, stale_player, _ = join_party(db_session, party.invite_code, "Landmine")
    stale_player.last_seen_at = datetime.now(UTC) - timedelta(hours=2)
    db_session.commit()
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
    assert b"Away" in response.body
    assert b"data-confirm-remove-player" in response.body


def test_party_room_renders_leave_party_for_non_leader(db_session) -> None:
    party, _, _ = create_party(db_session, "Cipher")
    _, member, token = join_party(db_session, party.invite_code, "Landmine")
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": f"/party/{party.id}",
            "headers": [],
            "app": app,
        }
    )

    response = party_room(request, party.id, encode_session_cookie(member.id, token), db_session)

    assert response.status_code == 200
    assert b"Leave Party" in response.body
    assert b'id="leave-party-modal"' in response.body
    assert b'class="nav-leave-form"' in response.body
    assert b'<button class="nav-leave-button" type="submit">Leave</button>' in response.body


def test_party_room_renders_leave_party_for_promoted_slot_two_leader(db_session) -> None:
    party, leader, _ = create_party(db_session, "Cipher")
    _, promoted_leader, token = join_party(db_session, party.invite_code, "Landmine")
    join_party(db_session, party.invite_code, "Kaos")
    leave_party(db_session, party, leader)
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": f"/party/{party.id}",
            "headers": [],
            "app": app,
        }
    )

    response = party_room(
        request,
        party.id,
        encode_session_cookie(promoted_leader.id, token),
        db_session,
    )

    assert response.status_code == 200
    assert b'<button class="nav-leave-button" type="submit">Leave</button>' in response.body


def test_party_room_shows_removed_player_notice(db_session) -> None:
    party, leader, _ = create_party(db_session, "Cipher")
    _, removed_player, removed_token = join_party(db_session, party.invite_code, "Landmine")
    remove_player_from_party(db_session, party, leader, removed_player.id)
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": f"/party/{party.id}",
            "headers": [],
            "app": app,
        }
    )

    response = party_room(
        request,
        party.id,
        encode_session_cookie(removed_player.id, removed_token),
        db_session,
    )

    assert response.status_code == 403
    assert b"Removed From Warparty" in response.body
    assert b"You were removed from this Warparty" in response.body
    assert b"The invite code has changed" in response.body
    assert b"Ask the party leader for a new invite" in response.body
    assert b"Player War Plans" not in response.body
    assert b"Recommended Party Route" not in response.body
    assert f"/join/{party.invite_code}".encode() not in response.body


def test_party_room_live_removed_player_gets_notice_without_party_state(db_session) -> None:
    party, leader, _ = create_party(db_session, "Cipher")
    _, removed_player, removed_token = join_party(db_session, party.invite_code, "Landmine")
    remove_player_from_party(db_session, party, leader, removed_player.id)
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": f"/party/{party.id}/live",
            "headers": [],
            "app": app,
        }
    )

    response = party_room_live(
        request,
        party.id,
        encode_session_cookie(removed_player.id, removed_token),
        db_session,
    )

    assert response.status_code == 200
    assert b"data-party-access-denied" in response.body
    assert b"Removed From Warparty" in response.body
    assert b"Player War Plans" not in response.body
    assert b"Recommended Party Route" not in response.body


def test_my_warplan_without_current_player_redirects_without_invite(db_session) -> None:
    party, _, _ = create_party(db_session, "Cipher")
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": f"/party/{party.id}/my-warplan",
            "headers": [],
            "app": app,
        }
    )

    response = my_warplan(request, party.id, None, db_session)

    assert response.status_code == 303
    assert response.headers["location"] == f"/party/{party.id}"
    assert party.invite_code not in response.headers["location"]


async def test_save_my_warplan_without_current_player_redirects_without_invite(
    db_session,
) -> None:
    party, _, _ = create_party(db_session, "Cipher")
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": f"/party/{party.id}/my-warplan",
            "headers": [],
            "app": app,
        }
    )

    response = await save_my_warplan(
        request,
        party.id,
        plan_length=1,
        progress_index=0,
        csrf_token="",
        activity_1="helltide",
        session_cookie=None,
        db=db_session,
    )

    assert response.status_code == 303
    assert response.headers["location"] == f"/party/{party.id}"
    assert party.invite_code not in response.headers["location"]


def test_route_marks_current_step(db_session) -> None:
    party, player, token = create_party(db_session, "Cipher")
    save_warplan(db_session, player, ["helltide", "pit"])
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
    assert b"route-card-next" in response.body
    assert b"Current" in response.body
    assert b"/progress/complete" not in response.body
    assert b"Mark Helltide complete" in response.body
    assert b'class="player-summary-line"' not in response.body


def test_current_player_ready_badge_is_hidden_and_plan_levels_are_clickable(
    db_session,
) -> None:
    party, player, token = create_party(db_session, "Cipher")
    save_warplan(db_session, player, ["helltide", "pit", "lair_boss"], progress_index=1)
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
    assert b'<span class="status-pill warning">You</span>' in response.body
    assert b'<span class="status-pill success">Ready</span>' not in response.body
    assert response.body.count(b"/progress/set") == 3
    assert b"Undo Helltide" in response.body
    assert b"Mark Pit complete" in response.body
    assert b"Complete through level 3: Lair Boss" in response.body
    assert b"data-shortcut-undo-progress" in response.body
    assert b"data-shortcut-mark-current" in response.body
    assert b"is-future" in response.body
    assert b"is-recommended" in response.body
    assert b"Undo Last" not in response.body


def test_other_ready_player_still_shows_ready_badge(db_session) -> None:
    party, leader, token = create_party(db_session, "Cipher")
    _, member, _ = join_party(db_session, party.invite_code, "Landmine")
    save_warplan(db_session, member, ["helltide"])
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
    assert b'<span class="status-pill success">Ready</span>' in response.body


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

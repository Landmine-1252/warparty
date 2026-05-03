from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Cookie, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.constants import (
    ACTIVITY_PICKER_ACTIVITIES,
    MAX_PLAN_LENGTH,
    activity_icon_path,
    activity_name,
)
from app.database import get_db
from app.realtime import manager
from app.security import (
    COOKIE_NAME,
    REMEMBERED_PLAYER_NAME_COOKIE,
    csrf_token_from_cookie,
    set_remembered_player_name_cookie,
    set_session_cookie,
    verify_csrf_token,
)
from app.services.errors import ServiceError
from app.services.invites import invite_url
from app.services.parties import (
    create_party,
    get_party,
    get_party_by_invite_code,
    join_party,
    party_is_full,
)
from app.services.players import get_current_player, remove_player_from_party
from app.services.routes import recommended_route_for_party
from app.services.warplans import (
    delete_warplan,
    get_activities,
    mark_current_complete,
    save_warplan,
    set_progress_index,
    undo_last_progress,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {"remembered_player_name": _remembered_player_name(request)},
    )


@router.post("/parties")
def create_party_page(
    player_name: str = Form(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        party, player, token = create_party(db, player_name)
    except ServiceError as exc:
        return _error_redirect(str(exc))
    response = RedirectResponse(f"/party/{party.id}", status_code=status.HTTP_303_SEE_OTHER)
    set_session_cookie(response, player.id, token)
    set_remembered_player_name_cookie(response, player.display_name)
    return response


@router.get("/join/{invite_code}", response_class=HTMLResponse)
def join_by_code(
    request: Request,
    invite_code: str,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    party = get_party_by_invite_code(db, invite_code)
    party_full = party_is_full(party) if party else False
    return templates.TemplateResponse(
        request,
        "join.html",
        {
            "invite_code": invite_code.upper(),
            "party": party,
            "party_full": party_full,
            "error": _join_page_error(party, party_full),
            "remembered_player_name": _remembered_player_name(request),
        },
    )


@router.post("/join", response_model=None)
async def join_party_page(
    request: Request,
    invite_code: str = Form(...),
    player_name: str = Form(...),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    party = get_party_by_invite_code(db, invite_code)
    if party is None:
        return _join_page_response(
            request,
            invite_code,
            None,
            "Invite code was not found.",
            status.HTTP_404_NOT_FOUND,
        )
    if party_is_full(party):
        return _join_page_response(
            request,
            invite_code,
            party,
            "This Warparty is full. Ask the party leader to remove someone, then try again.",
            status.HTTP_409_CONFLICT,
            party_full=True,
        )
    try:
        party, player, token = join_party(db, invite_code, player_name)
    except ServiceError as exc:
        return _join_page_response(
            request,
            invite_code,
            party,
            str(exc),
            status.HTTP_400_BAD_REQUEST,
        )
    response = RedirectResponse(f"/party/{party.id}", status_code=status.HTTP_303_SEE_OTHER)
    set_session_cookie(response, player.id, token)
    set_remembered_player_name_cookie(response, player.display_name)
    await manager.broadcast(party.id, "player_joined")
    return response


@router.get("/party/{party_id}", response_class=HTMLResponse)
def party_room(
    request: Request,
    party_id: str,
    session_cookie: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    party = get_party(db, party_id)
    if party is None:
        return _error_page(request, "Warparty not found.", status.HTTP_404_NOT_FOUND)
    current_player = get_current_player(db, party_id, session_cookie)
    route = recommended_route_for_party(party)
    return templates.TemplateResponse(
        request,
        "party.html",
        _party_context(request, party, current_player, route, session_cookie),
    )


@router.post("/party/{party_id}/progress/complete")
async def complete_progress_page(
    party_id: str,
    csrf_token: str = Form(""),
    session_cookie: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    player = get_current_player(db, party_id, session_cookie)
    if player is None or not verify_csrf_token(session_cookie, party_id, csrf_token):
        return RedirectResponse(f"/party/{party_id}", status_code=status.HTTP_303_SEE_OTHER)
    try:
        mark_current_complete(db, player)
    except ServiceError:
        return RedirectResponse(f"/party/{party_id}", status_code=status.HTTP_303_SEE_OTHER)
    await manager.broadcast(party_id, "progress_completed")
    return RedirectResponse(f"/party/{party_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/party/{party_id}/progress/undo")
async def undo_progress_page(
    party_id: str,
    csrf_token: str = Form(""),
    session_cookie: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    player = get_current_player(db, party_id, session_cookie)
    if player is not None and verify_csrf_token(session_cookie, party_id, csrf_token):
        try:
            undo_last_progress(db, player)
        except ServiceError:
            pass
        await manager.broadcast(party_id, "progress_undone")
    return RedirectResponse(f"/party/{party_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/party/{party_id}/progress/set")
async def set_progress_page(
    party_id: str,
    progress_index: int = Form(...),
    csrf_token: str = Form(""),
    session_cookie: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    player = get_current_player(db, party_id, session_cookie)
    if player is not None and verify_csrf_token(session_cookie, party_id, csrf_token):
        try:
            set_progress_index(db, player, progress_index)
        except ServiceError:
            pass
        await manager.broadcast(party_id, "progress_set")
    return RedirectResponse(f"/party/{party_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/party/{party_id}/my-warplan", response_class=HTMLResponse)
def my_warplan(
    request: Request,
    party_id: str,
    session_cookie: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    party = get_party(db, party_id)
    if party is None:
        return _error_page(request, "Warparty not found.", status.HTTP_404_NOT_FOUND)
    current_player = get_current_player(db, party_id, session_cookie)
    if current_player is None:
        return templates.TemplateResponse(
            request,
            "join.html",
            {
                "invite_code": party.invite_code,
                "party": party,
                "party_full": party_is_full(party),
                "error": "Join this Warparty before editing a War Plan.",
                "remembered_player_name": _remembered_player_name(request),
            },
        )
    activities = get_activities(current_player.warplan)
    return templates.TemplateResponse(
        request,
        "my_warplan.html",
        {
            "party": party,
            "current_player": current_player,
            "activity_options": ACTIVITY_PICKER_ACTIVITIES,
            "activities": activities,
            "max_plan_length": MAX_PLAN_LENGTH,
            "progress_index": (
                current_player.warplan.progress_index if current_player.warplan else 0
            ),
            "csrf_token": csrf_token_from_cookie(session_cookie, party_id),
            "error": None,
        },
    )


@router.post("/party/{party_id}/my-warplan", response_model=None)
async def save_my_warplan(
    request: Request,
    party_id: str,
    plan_length: int = Form(...),
    progress_index: int = Form(0),
    csrf_token: str = Form(""),
    activity_1: str = Form(""),
    activity_2: str = Form(""),
    activity_3: str = Form(""),
    activity_4: str = Form(""),
    activity_5: str = Form(""),
    session_cookie: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    party = get_party(db, party_id)
    if party is None:
        return _error_page(request, "Warparty not found.", status.HTTP_404_NOT_FOUND)
    current_player = get_current_player(db, party_id, session_cookie)
    if current_player is None:
        return RedirectResponse(f"/join/{party.invite_code}", status_code=status.HTTP_303_SEE_OTHER)
    if not verify_csrf_token(session_cookie, party_id, csrf_token):
        return _error_page(
            request,
            "Security token expired. Refresh and try again.",
            status.HTTP_403_FORBIDDEN,
        )

    selected = [activity_1, activity_2, activity_3, activity_4, activity_5][:plan_length]
    try:
        save_warplan(db, current_player, selected, progress_index)
    except ServiceError as exc:
        return templates.TemplateResponse(
            request,
            "my_warplan.html",
            {
                "party": party,
                "current_player": current_player,
                "activity_options": ACTIVITY_PICKER_ACTIVITIES,
                "activities": selected,
                "max_plan_length": MAX_PLAN_LENGTH,
                "progress_index": progress_index,
                "csrf_token": csrf_token_from_cookie(session_cookie, party_id),
                "error": str(exc),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    await manager.broadcast(party_id, "warplan_saved")
    return RedirectResponse(f"/party/{party_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/party/{party_id}/my-warplan/delete")
async def delete_my_warplan(
    party_id: str,
    csrf_token: str = Form(""),
    session_cookie: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    current_player = get_current_player(db, party_id, session_cookie)
    if current_player is not None and verify_csrf_token(session_cookie, party_id, csrf_token):
        delete_warplan(db, current_player)
        await manager.broadcast(party_id, "warplan_deleted")
    return RedirectResponse(f"/party/{party_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/party/{party_id}/players/{player_id}/remove")
async def remove_player_page(
    party_id: str,
    player_id: int,
    csrf_token: str = Form(""),
    session_cookie: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    party = get_party(db, party_id)
    current_player = get_current_player(db, party_id, session_cookie)
    if (
        party is not None
        and current_player is not None
        and verify_csrf_token(session_cookie, party_id, csrf_token)
    ):
        try:
            remove_player_from_party(db, party, current_player, player_id)
        except ServiceError:
            pass
        else:
            await manager.broadcast(party_id, "player_removed")
    return RedirectResponse(f"/party/{party_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
def readyz(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ready"}


def _party_context(
    request: Request,
    party: Any,
    current_player: Any,
    route: Any,
    session_cookie: str | None,
) -> dict[str, Any]:
    settings = get_settings()
    max_players = settings.max_players_per_party
    occupied_slots = {player.slot_number for player in party.players}
    slots = [
        next((player for player in party.players if player.slot_number == slot), None)
        for slot in range(1, max_players + 1)
    ]
    ready_players = [player for player in party.players if player.warplan is not None]
    is_party_leader = current_player is not None and party.leader_player_id == current_player.id
    return {
        "request": request,
        "party": party,
        "current_player": current_player,
        "route": route,
        "slots": slots,
        "open_slots": max_players - len(occupied_slots),
        "ready_players_count": len(ready_players),
        "invite_url": invite_url(party),
        "activity_options": ACTIVITY_PICKER_ACTIVITIES,
        "activity_name": activity_name,
        "activity_icon_path": activity_icon_path,
        "get_activities": get_activities,
        "is_party_leader": is_party_leader,
        "next_action": _next_action(current_player, ready_players, route),
        "csrf_token": csrf_token_from_cookie(session_cookie, party.id) if current_player else None,
    }


def _next_action(current_player: Any, ready_players: list[Any], route: list[Any]) -> dict[str, Any]:
    if not ready_players:
        return {
            "state": "waiting",
            "title": "Waiting for plans",
            "message": "Players need to enter War Plans before a shared route can be built.",
            "button": "Refresh",
        }
    if not route:
        return {
            "state": "complete",
            "title": "Route Complete",
            "message": "Everyone has completed the recommended route.",
            "button": None,
        }
    step = route[0]
    if current_player is None:
        return {
            "state": "readonly",
            "title": f"Next: {step.activity_name}",
            "message": step.instruction_text,
            "button": "Join to track progress",
            "step": step,
        }
    if current_player.id in step.advancing_player_ids:
        return {
            "state": "act",
            "title": f"Next: {step.activity_name}",
            "message": step.instruction_text,
            "button": f"Mark {step.activity_name} Complete",
            "step": step,
        }
    if step.advancing_player_names:
        actor = ", ".join(step.advancing_player_names)
        return {
            "state": "synced",
            "title": f"Next: {step.activity_name}",
            "message": f"{actor} advances.",
            "button": "Refresh",
            "step": step,
        }
    return {
        "state": "waiting",
        "title": "Waiting for plans",
        "message": "Refresh after players update their plans.",
        "button": "Refresh",
    }


def _error_redirect(message: str) -> RedirectResponse:
    return RedirectResponse(
        f"/?{urlencode({'error': message})}", status_code=status.HTTP_303_SEE_OTHER
    )


def _error_page(request: Request, message: str, status_code: int) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "error.html",
        {"message": message},
        status_code=status_code,
    )


def _remembered_player_name(request: Request) -> str:
    return request.cookies.get(REMEMBERED_PLAYER_NAME_COOKIE, "")


def _join_page_error(party: Any, party_full: bool) -> str | None:
    if party is None:
        return "Invite code was not found."
    if party_full:
        return "This Warparty is full. Ask the party leader to remove someone, then try again."
    return None


def _join_page_response(
    request: Request,
    invite_code: str,
    party: Any,
    error: str,
    status_code: int,
    *,
    party_full: bool = False,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "join.html",
        {
            "invite_code": invite_code.strip().upper(),
            "party": party,
            "party_full": party_full,
            "error": error,
            "remembered_player_name": _remembered_player_name(request),
        },
        status_code=status_code,
    )

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Cookie, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import get_settings
from app.constants import ACTIVITIES, MAX_PLAN_LENGTH, activity_icon_path, activity_name
from app.database import get_db
from app.realtime import manager
from app.security import COOKIE_NAME, set_session_cookie
from app.services.errors import ServiceError
from app.services.invites import invite_url
from app.services.parties import create_party, get_party, get_party_by_invite_code, join_party
from app.services.players import get_current_player
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
    return templates.TemplateResponse(request, "index.html", {})


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
    return response


@router.get("/join/{invite_code}", response_class=HTMLResponse)
def join_by_code(
    request: Request,
    invite_code: str,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    party = get_party_by_invite_code(db, invite_code)
    return templates.TemplateResponse(
        request,
        "join.html",
        {
            "invite_code": invite_code.upper(),
            "party": party,
            "error": None if party else "Invite code was not found.",
        },
    )


@router.post("/join")
async def join_party_page(
    invite_code: str = Form(...),
    player_name: str = Form(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        party, player, token = join_party(db, invite_code, player_name)
    except ServiceError as exc:
        return _error_redirect(str(exc))
    response = RedirectResponse(f"/party/{party.id}", status_code=status.HTTP_303_SEE_OTHER)
    set_session_cookie(response, player.id, token)
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
        _party_context(request, party, current_player, route),
    )


@router.post("/party/{party_id}/progress/complete")
async def complete_progress_page(
    party_id: str,
    session_cookie: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    player = get_current_player(db, party_id, session_cookie)
    if player is None:
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
    session_cookie: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    player = get_current_player(db, party_id, session_cookie)
    if player is not None:
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
    session_cookie: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    player = get_current_player(db, party_id, session_cookie)
    if player is not None:
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
                "error": "Join this Warparty before editing a War Plan.",
            },
        )
    activities = get_activities(current_player.warplan)
    return templates.TemplateResponse(
        request,
        "my_warplan.html",
        {
            "party": party,
            "current_player": current_player,
            "activity_options": ACTIVITIES,
            "activities": activities,
            "max_plan_length": MAX_PLAN_LENGTH,
            "progress_index": (
                current_player.warplan.progress_index if current_player.warplan else 0
            ),
            "error": None,
        },
    )


@router.post("/party/{party_id}/my-warplan", response_model=None)
async def save_my_warplan(
    request: Request,
    party_id: str,
    plan_length: int = Form(...),
    progress_index: int = Form(0),
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
                "activity_options": ACTIVITIES,
                "activities": selected,
                "max_plan_length": MAX_PLAN_LENGTH,
                "progress_index": progress_index,
                "error": str(exc),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    await manager.broadcast(party_id, "warplan_saved")
    return RedirectResponse(f"/party/{party_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/party/{party_id}/my-warplan/delete")
async def delete_my_warplan(
    party_id: str,
    session_cookie: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    current_player = get_current_player(db, party_id, session_cookie)
    if current_player is not None:
        delete_warplan(db, current_player)
        await manager.broadcast(party_id, "warplan_deleted")
    return RedirectResponse(f"/party/{party_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


def _party_context(request: Request, party: Any, current_player: Any, route: Any) -> dict[str, Any]:
    settings = get_settings()
    max_players = settings.max_players_per_party
    occupied_slots = {player.slot_number for player in party.players}
    slots = [
        next((player for player in party.players if player.slot_number == slot), None)
        for slot in range(1, max_players + 1)
    ]
    ready_players = [player for player in party.players if player.warplan is not None]
    return {
        "request": request,
        "party": party,
        "current_player": current_player,
        "route": route,
        "slots": slots,
        "open_slots": max_players - len(occupied_slots),
        "ready_players_count": len(ready_players),
        "invite_url": invite_url(party),
        "activity_options": ACTIVITIES,
        "activity_name": activity_name,
        "activity_icon_path": activity_icon_path,
        "get_activities": get_activities,
        "next_action": _next_action(current_player, ready_players, route),
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
    return RedirectResponse(f"/?error={message}", status_code=status.HTTP_303_SEE_OTHER)


def _error_page(request: Request, message: str, status_code: int) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "error.html",
        {"message": message},
        status_code=status_code,
    )

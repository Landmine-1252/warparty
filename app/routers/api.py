from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.realtime import manager
from app.schemas import (
    PartyCreateRequest,
    PartyJoinRequest,
    PartyResponse,
    ProgressSetRequest,
    RouteStepResponse,
    WarPlanSaveRequest,
)
from app.security import COOKIE_NAME, set_session_cookie
from app.services.errors import ServiceError
from app.services.parties import create_party, get_party, join_party
from app.services.players import get_current_player
from app.services.routes import recommended_route_for_party
from app.services.serializers import party_response, route_response
from app.services.warplans import (
    delete_warplan,
    mark_current_complete,
    save_warplan,
    set_progress_index,
    undo_last_progress,
)

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/parties/{party_id}", response_model=PartyResponse)
def get_party_json(party_id: str, db: Session = Depends(get_db)) -> PartyResponse:
    party = get_party(db, party_id)
    if party is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return party_response(party)


@router.get("/parties/{party_id}/route", response_model=list[RouteStepResponse])
def get_party_route_json(
    party_id: str,
    db: Session = Depends(get_db),
) -> list[RouteStepResponse]:
    party = get_party(db, party_id)
    if party is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return route_response(recommended_route_for_party(party))


@router.post("/parties", response_model=PartyResponse, status_code=status.HTTP_201_CREATED)
def create_party_json(
    request: PartyCreateRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> PartyResponse:
    try:
        party, player, token = create_party(db, request.player_name)
    except ServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    set_session_cookie(response, player.id, token)
    return party_response(party)


@router.post("/parties/{party_id}/join", response_model=PartyResponse)
async def join_party_json(
    party_id: str,
    request: PartyJoinRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> PartyResponse:
    party = get_party(db, party_id)
    if party is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if party.invite_code != request.invite_code.strip().upper():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite code mismatch.")
    try:
        party, player, token = join_party(db, request.invite_code, request.player_name)
    except ServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    set_session_cookie(response, player.id, token)
    await manager.broadcast(party.id, "player_joined")
    return party_response(party)


@router.post("/parties/{party_id}/warplan", response_model=PartyResponse)
async def save_warplan_json(
    party_id: str,
    request: WarPlanSaveRequest,
    session_cookie: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(get_db),
) -> PartyResponse:
    player = _require_current_player(db, party_id, session_cookie)
    try:
        save_warplan(db, player, request.activities, request.progress_index)
    except ServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await manager.broadcast(party_id, "warplan_saved")
    party = get_party(db, party_id)
    if party is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return party_response(party)


@router.delete("/parties/{party_id}/warplan", status_code=status.HTTP_204_NO_CONTENT)
async def delete_warplan_json(
    party_id: str,
    session_cookie: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(get_db),
) -> Response:
    player = _require_current_player(db, party_id, session_cookie)
    delete_warplan(db, player)
    await manager.broadcast(party_id, "warplan_deleted")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/parties/{party_id}/progress/complete", response_model=PartyResponse)
async def complete_progress_json(
    party_id: str,
    session_cookie: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(get_db),
) -> PartyResponse:
    player = _require_current_player(db, party_id, session_cookie)
    try:
        mark_current_complete(db, player)
    except ServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await manager.broadcast(party_id, "progress_completed")
    party = get_party(db, party_id)
    if party is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return party_response(party)


@router.post("/parties/{party_id}/progress/undo", response_model=PartyResponse)
async def undo_progress_json(
    party_id: str,
    session_cookie: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(get_db),
) -> PartyResponse:
    player = _require_current_player(db, party_id, session_cookie)
    try:
        undo_last_progress(db, player)
    except ServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await manager.broadcast(party_id, "progress_undone")
    party = get_party(db, party_id)
    if party is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return party_response(party)


@router.post("/parties/{party_id}/progress/set", response_model=PartyResponse)
async def set_progress_json(
    party_id: str,
    request: ProgressSetRequest,
    session_cookie: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(get_db),
) -> PartyResponse:
    player = _require_current_player(db, party_id, session_cookie)
    try:
        set_progress_index(db, player, request.progress_index)
    except ServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await manager.broadcast(party_id, "progress_set")
    party = get_party(db, party_id)
    if party is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return party_response(party)


def _require_current_player(
    db: Session,
    party_id: str,
    session_cookie: str | None,
):
    player = get_current_player(db, party_id, session_cookie)
    if player is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Join this party before editing progress.",
        )
    return player

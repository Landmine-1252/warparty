from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.database import SessionLocal
from app.realtime import manager
from app.security import COOKIE_NAME
from app.services.parties import get_party
from app.services.players import get_current_player

router = APIRouter()


@router.websocket("/ws/party/{party_id}")
async def party_updates(websocket: WebSocket, party_id: str) -> None:
    with SessionLocal() as db:
        party = get_party(db, party_id)
        current_player = get_current_player(db, party_id, websocket.cookies.get(COOKIE_NAME))
        if party is None or current_player is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    await manager.connect(party_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(party_id, websocket)

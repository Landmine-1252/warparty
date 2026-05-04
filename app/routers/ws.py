from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.realtime import manager

router = APIRouter()


@router.websocket("/ws/party/{party_id}")
async def party_updates(websocket: WebSocket, party_id: str) -> None:
    await manager.connect(party_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(party_id, websocket)

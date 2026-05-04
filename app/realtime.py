from __future__ import annotations

from collections import defaultdict

from fastapi import WebSocket, WebSocketDisconnect


class PartyConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, party_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[party_id].add(websocket)

    def disconnect(self, party_id: str, websocket: WebSocket) -> None:
        connections = self._connections.get(party_id)
        if not connections:
            return
        connections.discard(websocket)
        if not connections:
            self._connections.pop(party_id, None)

    async def broadcast(self, party_id: str, reason: str) -> None:
        message = {
            "type": "party_updated",
            "party_id": party_id,
            "reason": reason,
        }
        stale: list[WebSocket] = []
        for websocket in list(self._connections.get(party_id, set())):
            try:
                await websocket.send_json(message)
            except (RuntimeError, WebSocketDisconnect):
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(party_id, websocket)

    def count(self, party_id: str) -> int:
        return len(self._connections.get(party_id, set()))


manager = PartyConnectionManager()

from __future__ import annotations

from app.realtime import PartyConnectionManager


class FakeWebSocket:
    def __init__(self) -> None:
        self.accepted = False
        self.messages: list[dict[str, str]] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict[str, str]) -> None:
        self.messages.append(message)


async def test_broadcast_manager_registers_unregisters_and_broadcasts() -> None:
    manager = PartyConnectionManager()
    websocket = FakeWebSocket()

    await manager.connect("party-1", websocket)
    assert websocket.accepted is True
    assert manager.count("party-1") == 1

    await manager.broadcast("party-1", "warplan_saved")
    assert websocket.messages == [
        {
            "type": "party_updated",
            "party_id": "party-1",
            "reason": "warplan_saved",
        }
    ]

    manager.disconnect("party-1", websocket)
    assert manager.count("party-1") == 0

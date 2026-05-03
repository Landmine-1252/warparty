from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Player, utcnow
from app.security import decode_session_cookie, verify_session_token


def get_player(db: Session, player_id: int) -> Player | None:
    return db.get(Player, player_id)


def get_current_player(
    db: Session,
    party_id: str,
    session_cookie: str | None,
) -> Player | None:
    decoded = decode_session_cookie(session_cookie)
    if decoded is None:
        return None
    player_id, token = decoded
    player = db.scalar(select(Player).where(Player.id == player_id, Player.party_id == party_id))
    if player is None:
        return None
    if not verify_session_token(token, player.session_token_hash):
        return None
    player.last_seen_at = utcnow()
    db.commit()
    db.refresh(player)
    return player

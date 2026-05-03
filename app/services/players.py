from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Party, Player, utcnow
from app.security import decode_session_cookie, verify_session_token
from app.services.errors import ServiceError


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


def remove_player_from_party(
    db: Session,
    party: Party,
    acting_player: Player,
    target_player_id: int,
) -> None:
    if party.leader_player_id != acting_player.id:
        raise ServiceError("Only the party leader can remove players.")
    if target_player_id == acting_player.id:
        raise ServiceError("The party leader cannot remove themselves.")

    target_player = db.scalar(
        select(Player).where(Player.id == target_player_id, Player.party_id == party.id)
    )
    if target_player is None:
        raise ServiceError("Player was not found in this Warparty.")

    db.delete(target_player)
    db.commit()
    db.expire(party, ["players"])

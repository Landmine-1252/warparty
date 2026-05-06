from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Party, Player, utcnow
from app.security import decode_session_cookie, verify_session_token
from app.services.errors import ServiceError
from app.services.parties import rotate_party_invite_code

LAST_SEEN_WRITE_INTERVAL = timedelta(seconds=60)


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
    now = utcnow()
    if _should_update_last_seen(player.last_seen_at, now):
        player.last_seen_at = now
        db.commit()
        db.refresh(player)
    return player


def _should_update_last_seen(last_seen_at: datetime | None, now: datetime) -> bool:
    if last_seen_at is None:
        return True
    if last_seen_at.tzinfo is None:
        last_seen_at = last_seen_at.replace(tzinfo=UTC)
    return now - last_seen_at >= LAST_SEEN_WRITE_INTERVAL


def player_is_stale(player: Player, stale_minutes: int, *, now: datetime | None = None) -> bool:
    last_seen_at = player.last_seen_at
    if last_seen_at is None:
        return True
    if last_seen_at.tzinfo is None:
        last_seen_at = last_seen_at.replace(tzinfo=UTC)
    return (now or utcnow()) - last_seen_at > timedelta(minutes=stale_minutes)


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

    rotate_party_invite_code(db, party)
    db.delete(target_player)
    db.commit()
    db.refresh(party)
    db.expire(party, ["players"])


def claim_party_leadership(
    db: Session,
    party: Party,
    acting_player: Player,
    stale_minutes: int,
) -> Player:
    if acting_player.party_id != party.id:
        raise ServiceError("Player was not found in this Warparty.")
    if party.leader_player_id == acting_player.id:
        return acting_player
    if player_is_stale(acting_player, stale_minutes):
        raise ServiceError("Only an active player can claim leadership.")

    current_leader = (
        db.get(Player, party.leader_player_id) if party.leader_player_id is not None else None
    )
    if current_leader is not None and not player_is_stale(current_leader, stale_minutes):
        raise ServiceError("The current party leader is still active.")

    party.leader_player_id = acting_player.id
    db.commit()
    db.refresh(party)
    return acting_player


def leave_party(db: Session, party: Party, player: Player) -> None:
    if party.leader_player_id == player.id:
        successor = next(
            (
                party_player
                for party_player in sorted(party.players, key=lambda item: item.slot_number)
                if party_player.id != player.id
            ),
            None,
        )
        if successor is None:
            db.delete(party)
            db.commit()
            return
        party.leader_player_id = successor.id

    db.delete(player)
    db.commit()
    db.refresh(party)
    db.expire(party, ["players"])


def transfer_party_leader(
    db: Session,
    party: Party,
    acting_player: Player,
    target_player_id: int,
) -> Player:
    if party.leader_player_id != acting_player.id:
        raise ServiceError("Only the party leader can transfer leadership.")
    if target_player_id == acting_player.id:
        raise ServiceError("Choose another player to lead this Warparty.")

    target_player = db.scalar(
        select(Player).where(Player.id == target_player_id, Player.party_id == party.id)
    )
    if target_player is None:
        raise ServiceError("Player was not found in this Warparty.")

    party.leader_player_id = target_player.id
    db.commit()
    db.refresh(party)
    return target_player

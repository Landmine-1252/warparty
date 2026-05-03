from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.models import Party, Player
from app.security import (
    generate_invite_code,
    generate_public_id,
    generate_session_token,
    hash_session_token,
)
from app.services.errors import ServiceError


def create_party(db: Session, player_name: str) -> tuple[Party, Player, str]:
    display_name = _clean_player_name(player_name)
    party = Party(id=_unique_party_id(db), invite_code=_unique_invite_code(db))
    token = generate_session_token()
    player = Player(
        party=party,
        display_name=display_name,
        slot_number=1,
        session_token_hash=hash_session_token(token),
    )
    db.add(party)
    db.add(player)
    db.flush()
    party.leader_player_id = player.id
    db.commit()
    db.refresh(party)
    db.refresh(player)
    return party, player, token


def join_party(
    db: Session,
    invite_code: str,
    player_name: str,
    max_players: int | None = None,
) -> tuple[Party, Player, str]:
    party = get_party_by_invite_code(db, invite_code)
    if party is None:
        raise ServiceError("Invite code was not found.")
    max_slots = max_players or get_settings().max_players_per_party
    occupied_slots = {player.slot_number for player in party.players}
    open_slot = next((slot for slot in range(1, max_slots + 1) if slot not in occupied_slots), None)
    if open_slot is None:
        raise ServiceError("This Warparty is full.")

    token = generate_session_token()
    player = Player(
        party=party,
        display_name=_clean_player_name(player_name),
        slot_number=open_slot,
        session_token_hash=hash_session_token(token),
    )
    db.add(player)
    db.commit()
    db.refresh(party)
    db.refresh(player)
    return party, player, token


def get_party(db: Session, party_id: str) -> Party | None:
    return db.scalar(
        select(Party)
        .where(Party.id == party_id)
        .options(selectinload(Party.players).selectinload(Player.warplan))
    )


def get_party_by_invite_code(db: Session, invite_code: str) -> Party | None:
    return db.scalar(
        select(Party)
        .where(Party.invite_code == invite_code.strip().upper())
        .options(selectinload(Party.players).selectinload(Player.warplan))
    )


def party_is_full(party: Party, max_players: int | None = None) -> bool:
    max_slots = max_players or get_settings().max_players_per_party
    return len(party.players) >= max_slots


def _clean_player_name(player_name: str) -> str:
    display_name = " ".join(player_name.strip().split())
    if not display_name:
        raise ServiceError("Player name is required.")
    if len(display_name) > 40:
        raise ServiceError("Player name must be 40 characters or fewer.")
    return display_name


def _unique_party_id(db: Session) -> str:
    for _ in range(20):
        party_id = generate_public_id()
        if db.get(Party, party_id) is None:
            return party_id
    raise RuntimeError("Could not generate a unique party id.")


def _unique_invite_code(db: Session) -> str:
    for _ in range(20):
        invite_code = generate_invite_code()
        exists = db.scalar(select(Party.id).where(Party.invite_code == invite_code))
        if exists is None:
            return invite_code
    raise RuntimeError("Could not generate a unique invite code.")

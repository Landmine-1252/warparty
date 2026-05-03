from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Party(Base):
    __tablename__ = "parties"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    invite_code: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    leader_player_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    players: Mapped[list[Player]] = relationship(
        back_populates="party",
        cascade="all, delete-orphan",
        order_by="Player.slot_number",
    )


class Player(Base):
    __tablename__ = "players"
    __table_args__ = (UniqueConstraint("party_id", "slot_number", name="uq_player_party_slot"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    party_id: Mapped[str] = mapped_column(ForeignKey("parties.id"), index=True)
    display_name: Mapped[str] = mapped_column(String(40))
    slot_number: Mapped[int] = mapped_column(Integer)
    session_token_hash: Mapped[str] = mapped_column(String(128))
    is_connected: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    party: Mapped[Party] = relationship(back_populates="players")
    warplan: Mapped[WarPlan | None] = relationship(
        back_populates="player",
        cascade="all, delete-orphan",
        uselist=False,
    )


class WarPlan(Base):
    __tablename__ = "warplans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id"),
        unique=True,
        index=True,
    )
    activities_json: Mapped[str] = mapped_column(Text, default="[]")
    progress_index: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(24), default="manual")
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    player: Mapped[Player] = relationship(back_populates="warplan")

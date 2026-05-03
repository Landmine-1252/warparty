from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.constants import ACTIVITY_BY_KEY, MAX_PLAN_LENGTH, MIN_PLAN_LENGTH
from app.models import Player, WarPlan, utcnow
from app.services.errors import ServiceError

VALID_SOURCES = {"manual", "image_detected", "image_confirmed"}


def get_activities(warplan: WarPlan | None) -> list[str]:
    if warplan is None:
        return []
    raw = json.loads(warplan.activities_json or "[]")
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw]


def validate_activities(activities: list[str]) -> list[str]:
    cleaned = [activity.strip() for activity in activities if activity.strip()]
    if len(cleaned) < MIN_PLAN_LENGTH:
        raise ServiceError("Choose at least one activity.")
    if len(cleaned) > MAX_PLAN_LENGTH:
        raise ServiceError(f"War Plans can contain at most {MAX_PLAN_LENGTH} activities.")
    invalid = [activity for activity in cleaned if activity not in ACTIVITY_BY_KEY]
    if invalid:
        raise ServiceError(f"Unsupported activity: {invalid[0]}")
    return cleaned


def save_warplan(
    db: Session,
    player: Player,
    activities: list[str],
    progress_index: int = 0,
    source: str = "manual",
    confirmed_at: datetime | None = None,
) -> WarPlan:
    cleaned = validate_activities(activities)
    if progress_index < 0 or progress_index > len(cleaned):
        raise ServiceError("Progress must be between 0 and the War Plan length.")
    if source not in VALID_SOURCES:
        raise ServiceError("Invalid War Plan source.")

    warplan = player.warplan
    if warplan is None:
        warplan = WarPlan(player=player)
        db.add(warplan)
    warplan.activities_json = json.dumps(cleaned)
    warplan.progress_index = progress_index
    warplan.source = source
    warplan.confirmed_at = confirmed_at or utcnow()
    db.commit()
    db.refresh(warplan)
    return warplan


def delete_warplan(db: Session, player: Player) -> None:
    if player.warplan is None:
        return
    db.delete(player.warplan)
    db.commit()


def mark_current_complete(db: Session, player: Player) -> WarPlan:
    warplan = player.warplan
    if warplan is None:
        raise ServiceError("Create a War Plan before marking progress.")
    activities = get_activities(warplan)
    if warplan.progress_index >= len(activities):
        raise ServiceError("This War Plan is already complete.")
    warplan.progress_index += 1
    db.commit()
    db.refresh(warplan)
    return warplan


def set_progress_index(db: Session, player: Player, target_progress_index: int) -> WarPlan:
    warplan = player.warplan
    if warplan is None:
        raise ServiceError("Create a War Plan before marking progress.")
    activities = get_activities(warplan)
    if target_progress_index < 0 or target_progress_index > len(activities):
        raise ServiceError("Progress must be between 0 and the War Plan length.")
    if target_progress_index == warplan.progress_index:
        return warplan
    warplan.progress_index = target_progress_index
    db.commit()
    db.refresh(warplan)
    return warplan


def undo_last_progress(db: Session, player: Player) -> WarPlan:
    warplan = player.warplan
    if warplan is None:
        raise ServiceError("Create a War Plan before undoing progress.")
    if warplan.progress_index <= 0:
        raise ServiceError("There is no progress to undo.")
    warplan.progress_index -= 1
    db.commit()
    db.refresh(warplan)
    return warplan

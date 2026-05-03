from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Activity:
    key: str
    name: str
    icon_filename: str


ACTIVITIES: tuple[Activity, ...] = (
    Activity("helltide", "Helltide", "helltide.png"),
    Activity("pit", "Pit", "pit.png"),
    Activity("nightmare_dungeon", "Nightmare Dungeon", "nmd.png"),
    Activity("infernal_hordes", "Infernal Hordes", "infernal-horde.png"),
    Activity("lair_boss", "Lair Boss", "lairboss.png"),
    Activity("kurast_undercity", "Kurast Undercity", "undercity.png"),
)

ACTIVITY_BY_KEY: dict[str, Activity] = {activity.key: activity for activity in ACTIVITIES}
ACTIVITY_ORDER: tuple[str, ...] = tuple(activity.key for activity in ACTIVITIES)
ACTIVITY_PICKER_ORDER: tuple[str, ...] = (
    "helltide",
    "nightmare_dungeon",
    "lair_boss",
    "infernal_hordes",
    "pit",
    "kurast_undercity",
)
ACTIVITY_PICKER_ACTIVITIES: tuple[Activity, ...] = tuple(
    ACTIVITY_BY_KEY[activity_key] for activity_key in ACTIVITY_PICKER_ORDER
)
MAX_PLAN_LENGTH = 5
MIN_PLAN_LENGTH = 1


def activity_name(activity_key: str) -> str:
    return ACTIVITY_BY_KEY[activity_key].name


def activity_icon_path(activity_key: str) -> str:
    return f"/static/icons/warplan/{ACTIVITY_BY_KEY[activity_key].icon_filename}"

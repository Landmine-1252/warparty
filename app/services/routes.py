from __future__ import annotations

from app.config import get_settings
from app.models import Party
from app.planner import PlayerPlan, RouteStep, compute_recommended_route
from app.services.players import player_is_stale
from app.services.warplans import get_activities


def recommended_route_for_party(party: Party, *, include_away: bool = False) -> list[RouteStep]:
    settings = get_settings()
    plans: list[PlayerPlan] = []
    for player in party.players:
        if not include_away and player_is_stale(player, settings.stale_player_minutes):
            continue
        activities = get_activities(player.warplan)
        if not activities:
            continue
        progress_index = player.warplan.progress_index if player.warplan else 0
        plans.append(
            PlayerPlan(
                player_id=player.id,
                player_name=player.display_name,
                activities=tuple(activities),
                progress_index=progress_index,
            )
        )
    return compute_recommended_route(plans)

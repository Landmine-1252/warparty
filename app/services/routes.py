from __future__ import annotations

from app.models import Party
from app.planner import PlayerPlan, RouteStep, compute_recommended_route
from app.services.warplans import get_activities


def recommended_route_for_party(party: Party) -> list[RouteStep]:
    plans: list[PlayerPlan] = []
    for player in party.players:
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

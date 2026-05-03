from __future__ import annotations

from app.models import Party
from app.planner import RouteStep
from app.schemas import PartyResponse, PlayerResponse, RouteStepResponse
from app.services.warplans import get_activities


def party_response(party: Party) -> PartyResponse:
    return PartyResponse(
        id=party.id,
        invite_code=party.invite_code,
        leader_player_id=party.leader_player_id,
        players=[
            PlayerResponse(
                id=player.id,
                display_name=player.display_name,
                slot_number=player.slot_number,
                has_plan=player.warplan is not None,
                activities=get_activities(player.warplan),
                progress_index=player.warplan.progress_index if player.warplan else 0,
            )
            for player in party.players
        ],
    )


def route_response(route: list[RouteStep]) -> list[RouteStepResponse]:
    return [
        RouteStepResponse(
            step_number=step.step_number,
            activity_key=step.activity_key,
            activity_name=step.activity_name,
            step_type=step.step_type,
            advancing_player_ids=list(step.advancing_player_ids),
            advancing_player_names=list(step.advancing_player_names),
            waiting_player_ids=list(step.waiting_player_ids),
            waiting_player_names=list(step.waiting_player_names),
            instruction_text=step.instruction_text,
            is_current=step.is_current,
        )
        for step in route
    ]

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from app.constants import ACTIVITY_ORDER, activity_name


@dataclass(frozen=True)
class PlayerPlan:
    player_id: int
    player_name: str
    activities: tuple[str, ...]
    progress_index: int = 0


@dataclass(frozen=True)
class RouteStep:
    step_number: int
    activity_key: str
    activity_name: str
    step_type: str
    advancing_player_ids: tuple[int, ...]
    advancing_player_names: tuple[str, ...]
    waiting_player_ids: tuple[int, ...]
    waiting_player_names: tuple[str, ...]
    instruction_text: str
    is_current: bool


@dataclass(frozen=True)
class _Move:
    activity_key: str
    next_state: tuple[int, ...]
    advancing_indexes: tuple[int, ...]
    waiting_indexes: tuple[int, ...]


def compute_recommended_route(player_plans: list[PlayerPlan]) -> list[RouteStep]:
    active_plans = [
        plan
        for plan in sorted(player_plans, key=lambda item: item.player_id)
        if plan.activities and plan.progress_index < len(plan.activities)
    ]
    if not active_plans:
        return []

    start = tuple(min(plan.progress_index, len(plan.activities)) for plan in active_plans)
    goal = tuple(len(plan.activities) for plan in active_plans)
    parents: dict[tuple[int, ...], tuple[tuple[int, ...], _Move] | None] = {start: None}
    queue: deque[tuple[int, ...]] = deque([start])

    while queue:
        state = queue.popleft()
        if state == goal:
            break
        for move in _candidate_moves(active_plans, state):
            if move.next_state in parents:
                continue
            parents[move.next_state] = (state, move)
            queue.append(move.next_state)

    if goal not in parents:
        return []

    moves: list[_Move] = []
    state = goal
    while parents[state] is not None:
        previous_state, move = parents[state]
        moves.append(move)
        state = previous_state
    moves.reverse()

    return [
        _route_step(step_number, move, active_plans)
        for step_number, move in enumerate(moves, start=1)
    ]


def _candidate_moves(plans: list[PlayerPlan], state: tuple[int, ...]) -> list[_Move]:
    moves: list[_Move] = []
    for activity_key in ACTIVITY_ORDER:
        advancing: list[int] = []
        waiting: list[int] = []
        next_state = list(state)
        for index, plan in enumerate(plans):
            progress = state[index]
            if progress >= len(plan.activities):
                continue
            if plan.activities[progress] == activity_key:
                advancing.append(index)
                next_state[index] += 1
            else:
                waiting.append(index)
        if advancing:
            moves.append(
                _Move(
                    activity_key=activity_key,
                    next_state=tuple(next_state),
                    advancing_indexes=tuple(advancing),
                    waiting_indexes=tuple(waiting),
                )
            )

    return sorted(
        moves,
        key=lambda move: (
            -len(move.advancing_indexes),
            len(move.waiting_indexes),
            ACTIVITY_ORDER.index(move.activity_key),
        ),
    )


def _route_step(step_number: int, move: _Move, plans: list[PlayerPlan]) -> RouteStep:
    advancing_plans = [plans[index] for index in move.advancing_indexes]
    waiting_plans = [plans[index] for index in move.waiting_indexes]
    if len(advancing_plans) > 1:
        step_type = "shared"
    elif waiting_plans:
        step_type = "sync"
    else:
        step_type = "solo"

    advancing_names = tuple(plan.player_name for plan in advancing_plans)
    waiting_names = tuple(plan.player_name for plan in waiting_plans)
    return RouteStep(
        step_number=step_number,
        activity_key=move.activity_key,
        activity_name=activity_name(move.activity_key),
        step_type=step_type,
        advancing_player_ids=tuple(plan.player_id for plan in advancing_plans),
        advancing_player_names=advancing_names,
        waiting_player_ids=tuple(plan.player_id for plan in waiting_plans),
        waiting_player_names=waiting_names,
        instruction_text=_instruction(step_type, advancing_names, waiting_names),
        is_current=step_number == 1,
    )


def _join_names(names: tuple[str, ...]) -> str:
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{', '.join(names[:-1])}, and {names[-1]}"


def _instruction(
    step_type: str,
    advancing_names: tuple[str, ...],
    waiting_names: tuple[str, ...],
) -> str:
    advancing = _join_names(advancing_names)
    if step_type == "shared" and not waiting_names:
        return "Everyone progresses together."
    if step_type == "shared":
        return f"{advancing} progress."
    if waiting_names:
        return f"{advancing} advances."
    return f"{advancing} advances solo."

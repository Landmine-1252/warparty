from __future__ import annotations

from app.planner import PlayerPlan, compute_recommended_route


def test_shared_step_advances_multiple_players() -> None:
    route = compute_recommended_route(
        [
            PlayerPlan(1, "Cipher", ("helltide",)),
            PlayerPlan(2, "Landmine", ("helltide",)),
        ]
    )

    assert len(route) == 1
    assert route[0].step_type == "shared"
    assert route[0].advancing_player_ids == (1, 2)


def test_solo_step_advances_one_player() -> None:
    route = compute_recommended_route([PlayerPlan(1, "Cipher", ("pit",))])

    assert len(route) == 1
    assert route[0].step_type == "solo"
    assert route[0].advancing_player_ids == (1,)
    assert route[0].waiting_player_ids == ()


def test_ordered_progress_is_respected() -> None:
    route = compute_recommended_route(
        [
            PlayerPlan(1, "Cipher", ("pit", "helltide")),
            PlayerPlan(2, "Landmine", ("helltide",)),
        ]
    )

    assert [step.activity_key for step in route] == ["pit", "helltide"]
    assert route[0].advancing_player_ids == (1,)
    assert route[1].advancing_player_ids == (1, 2)


def test_future_steps_do_not_advance_early() -> None:
    route = compute_recommended_route(
        [
            PlayerPlan(1, "Cipher", ("pit", "helltide")),
            PlayerPlan(2, "Landmine", ("helltide",)),
        ]
    )

    assert route[0].activity_key == "pit"
    assert route[0].advancing_player_ids == (1,)
    first_helltide = next(step for step in route if step.activity_key == "helltide")
    assert first_helltide.activity_key == "helltide"
    assert 1 in first_helltide.advancing_player_ids


def test_bfs_minimizes_total_runs_better_than_player_by_player() -> None:
    route = compute_recommended_route(
        [
            PlayerPlan(1, "Cipher", ("lair_boss", "helltide")),
            PlayerPlan(2, "Landmine", ("helltide",)),
        ]
    )

    assert [step.activity_key for step in route] == ["lair_boss", "helltide"]
    assert len(route) == 2


def test_tie_breakers_are_deterministic_by_activity_order() -> None:
    route = compute_recommended_route(
        [
            PlayerPlan(1, "Cipher", ("pit",)),
            PlayerPlan(2, "Landmine", ("helltide",)),
        ]
    )

    assert [step.activity_key for step in route] == ["helltide", "pit"]


def test_sync_instruction_keeps_party_moving_forward() -> None:
    route = compute_recommended_route(
        [
            PlayerPlan(1, "Cipher", ("pit", "helltide")),
            PlayerPlan(2, "Landmine", ("helltide",)),
        ]
    )

    assert route[0].step_type == "sync"
    assert route[0].instruction_text == "Cipher advances."

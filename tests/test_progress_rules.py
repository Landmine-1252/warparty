from __future__ import annotations

import pytest

from app.services.errors import ServiceError
from app.services.parties import create_party, join_party
from app.services.warplans import (
    get_activities,
    mark_current_complete,
    save_warplan,
    set_progress_index,
    undo_last_progress,
)


def test_mark_complete_increments_only_current_player(db_session) -> None:
    party, player_one, _ = create_party(db_session, "Cipher")
    _, player_two, _ = join_party(db_session, party.invite_code, "Landmine")
    save_warplan(db_session, player_one, ["helltide", "pit"])
    save_warplan(db_session, player_two, ["helltide", "pit"])

    mark_current_complete(db_session, player_one)

    assert player_one.warplan.progress_index == 1
    assert player_two.warplan.progress_index == 0


def test_cannot_mark_complete_past_plan_end(db_session) -> None:
    _, player, _ = create_party(db_session, "Cipher")
    save_warplan(db_session, player, ["helltide"], progress_index=1)

    with pytest.raises(ServiceError):
        mark_current_complete(db_session, player)


def test_set_progress_can_complete_through_future_level(db_session) -> None:
    _, player, _ = create_party(db_session, "Cipher")
    save_warplan(db_session, player, ["helltide", "pit", "lair_boss"])

    set_progress_index(db_session, player, 3)

    assert player.warplan.progress_index == 3


def test_set_progress_can_undo_clicked_completed_level(db_session) -> None:
    _, player, _ = create_party(db_session, "Cipher")
    save_warplan(db_session, player, ["helltide", "pit", "lair_boss"], progress_index=2)

    set_progress_index(db_session, player, 1)

    assert player.warplan.progress_index == 1


def test_undo_decrements_by_one(db_session) -> None:
    _, player, _ = create_party(db_session, "Cipher")
    save_warplan(db_session, player, ["helltide", "pit"], progress_index=2)

    undo_last_progress(db_session, player)

    assert player.warplan.progress_index == 1


def test_cannot_undo_below_zero(db_session) -> None:
    _, player, _ = create_party(db_session, "Cipher")
    save_warplan(db_session, player, ["helltide"], progress_index=0)

    with pytest.raises(ServiceError):
        undo_last_progress(db_session, player)


def test_cannot_skip_ahead_when_saving_progress(db_session) -> None:
    _, player, _ = create_party(db_session, "Cipher")

    with pytest.raises(ServiceError):
        save_warplan(db_session, player, ["helltide"], progress_index=2)


def test_save_warplan_validates_activity_keys(db_session) -> None:
    _, player, _ = create_party(db_session, "Cipher")

    with pytest.raises(ServiceError):
        save_warplan(db_session, player, ["rift"])

    assert get_activities(player.warplan) == []

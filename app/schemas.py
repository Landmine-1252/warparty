from __future__ import annotations

from pydantic import BaseModel, Field

from app.constants import MAX_PLAN_LENGTH, MIN_PLAN_LENGTH


class PartyCreateRequest(BaseModel):
    player_name: str = Field(min_length=1, max_length=40)


class PartyJoinRequest(BaseModel):
    invite_code: str = Field(min_length=1, max_length=12)
    player_name: str = Field(min_length=1, max_length=40)


class WarPlanSaveRequest(BaseModel):
    activities: list[str] = Field(min_length=MIN_PLAN_LENGTH, max_length=MAX_PLAN_LENGTH)
    progress_index: int = Field(default=0, ge=0)


class ProgressSetRequest(BaseModel):
    progress_index: int = Field(ge=0)


class PlayerResponse(BaseModel):
    id: int
    display_name: str
    slot_number: int
    has_plan: bool
    activities: list[str]
    progress_index: int


class PartyResponse(BaseModel):
    id: str
    invite_code: str
    leader_player_id: int | None
    players: list[PlayerResponse]


class RouteStepResponse(BaseModel):
    step_number: int
    activity_key: str
    activity_name: str
    step_type: str
    advancing_player_ids: list[int]
    advancing_player_names: list[str]
    waiting_player_ids: list[int]
    waiting_player_names: list[str]
    instruction_text: str
    is_current: bool

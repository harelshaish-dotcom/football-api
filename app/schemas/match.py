from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MatchStatus = Literal["scheduled", "live", "finished"]


class MatchCreate(BaseModel):
    """Body of POST /matches."""

    home_team_id: int
    away_team_id: int
    matchday: int = Field(..., gt=0)
    status: MatchStatus = "scheduled"
    kickoff_time: datetime
    home_score: int = Field(default=0, ge=0)
    away_score: int = Field(default=0, ge=0)


class MatchUpdate(BaseModel):
    """Body of PATCH /matches/{id}; every field is optional."""

    home_team_id: int | None = None
    away_team_id: int | None = None
    matchday: int | None = Field(None, gt=0)
    status: MatchStatus | None = None
    kickoff_time: datetime | None = None
    home_score: int | None = Field(None, ge=0)
    away_score: int | None = Field(None, ge=0)


class MatchOut(BaseModel):
    """A match as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    home_team_id: int
    away_team_id: int
    home_score: int
    away_score: int
    matchday: int
    status: str
    kickoff_time: datetime
    created_at: datetime | None = None

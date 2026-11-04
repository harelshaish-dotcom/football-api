from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TeamCreate(BaseModel):
    """Body of POST /teams."""

    name: str = Field(min_length=2, max_length=60)
    league_id: int
    date_founded: datetime
    stadium: str | None = None


class TeamUpdate(BaseModel):
    """Body of PATCH /teams/{id}; every field is optional."""

    name: str | None = None
    league_id: int | None = None
    date_founded: datetime | None = None
    stadium: str | None = None


class TeamOut(BaseModel):
    """A team as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    league_id: int
    date_founded: datetime
    stadium: str | None = None
    created_at: datetime

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LeagueCreate(BaseModel):
    """Body of POST /leagues."""

    name: str = Field(min_length=2, max_length=100)
    country: str = Field(max_length=50)
    date_founded: datetime


class LeagueUpdate(BaseModel):
    """Body of PATCH /leagues/{id}; every field is optional."""

    name: str | None = Field(None, min_length=2, max_length=100)
    country: str | None = Field(None, max_length=50)
    date_founded: datetime | None = None


class LeagueOut(BaseModel):
    """A league as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    country: str
    date_founded: datetime

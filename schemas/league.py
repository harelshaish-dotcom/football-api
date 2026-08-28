from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime


class LeagueCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    country: str = Field(max_length=50)
    date_founded: datetime


class LeagueUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    country: str | None = Field(None, max_length=50)
    date_founded: datetime | None = None


class LeagueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    league_id: int
    name: str
    country: str
    date_founded: datetime
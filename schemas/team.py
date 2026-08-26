from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime



class TeamCreate(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    league_id: int
    founded: int | None = Field(None, ge=1850, le=2027)
    stadium: str | None = None


class TeamUpdate(BaseModel):
    name: str | None = None
    league_id: int | None = None
    founded: int | None = None
    stadium: str | None = None


class TeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    league_id: int
    founded: int | None = None
    stadium: str | None = None
    created_at: datetime
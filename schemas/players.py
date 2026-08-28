from pydantic import BaseModel, ConfigDict, Field, computed_field, field_serializer
from datetime import datetime
from models.enums import POSITIONS


class PlayerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    age: int
    position: str = Field(max_length=50)
    shirt_number: int
    height: int
    country: str = Field(max_length=50)
    value: int
    team_id: int


class PlayerUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    age: int | None = None
    position: str | None = Field(None, max_length=50)
    shirt_number: int | None = None
    height: int | None = None
    country: str | None = Field(None, max_length=50)
    value: int | None = None
    team_id: int | None = None

class PlayerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    name: str
    age: int
    position: str
    shirt_number: int
    height: int
    country: str
    value: int
    created_at: datetime
    team_id: int
    
    @field_serializer('position')
    def serialize_position(self, value: str):
        return POSITIONS.get(value, value)
# schemas/event.py
from pydantic import BaseModel
from typing import Literal

class PlayerRef(BaseModel):
    id: int
    name: str

class EventCreate(BaseModel):
    minute: int
    type: Literal["goal", "card", "substitution", "var"]
    player: PlayerRef
    detail: dict
    tags: list[str] = []
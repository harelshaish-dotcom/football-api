from typing import Literal

from pydantic import BaseModel


class PlayerRef(BaseModel):
    """The player an event is about, embedded in the event document."""

    id: int
    name: str


class EventCreate(BaseModel):
    """Body of POST /matches/{id}/events."""

    minute: int
    type: Literal["goal", "card", "substitution", "var"]
    player: PlayerRef
    detail: dict
    tags: list[str] = []

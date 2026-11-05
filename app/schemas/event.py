from typing import Literal

from pydantic import BaseModel, Field


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


class PlayerRefUpdate(BaseModel):
    """Partial update of the embedded player; only sent fields change."""

    id: int | None = None
    name: str | None = None


class EventUpdate(BaseModel):
    """Body of PATCH /matches/{id}/events/{event_id}. All fields optional."""

    minute: int | None = None
    type: Literal["goal", "card", "substitution", "var"] | None = None
    player: PlayerRefUpdate | None = None
    detail: dict | None = None


class TagCreate(BaseModel):
    """Body of POST /matches/{id}/events/{event_id}/tags."""

    tag: str = Field(min_length=1)

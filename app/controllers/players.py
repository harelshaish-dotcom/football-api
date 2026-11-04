"""Database operations for players."""

from sqlalchemy.orm import Session

from app.models.player import Player
from app.schemas.player import PlayerCreate, PlayerUpdate


def get_by_id(db: Session, player_id: int) -> Player | None:
    """Fetch one player by primary key."""
    return db.get(Player, player_id)


def list_players(
    db: Session, team_id: int | None, country: str | None, limit: int, offset: int
) -> tuple[list[Player], int]:
    """Return one page of players (optionally filtered by team and country) and the total."""
    q = db.query(Player)
    if team_id is not None:
        q = q.filter(Player.team_id == team_id)
    if country is not None:
        q = q.filter(Player.country == country)
    total = q.count()
    rows = q.order_by(Player.id).offset(offset).limit(limit).all()
    return rows, total


def create(db: Session, payload: PlayerCreate) -> Player:
    """Insert a new player."""
    player = Player(**payload.model_dump())
    db.add(player)
    db.commit()
    db.refresh(player)
    return player


def update(db: Session, player: Player, payload: PlayerUpdate) -> Player:
    """Apply only the fields that were sent in `payload`."""
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(player, field, value)
    db.commit()
    db.refresh(player)
    return player


def delete(db: Session, player: Player) -> None:
    """Delete a player."""
    db.delete(player)
    db.commit()

"""Database operations for teams."""

from sqlalchemy.orm import Session

from app.models.team import Team
from app.schemas.team import TeamCreate, TeamUpdate


def get_by_id(db: Session, team_id: int) -> Team | None:
    """Fetch one team by primary key."""
    return db.get(Team, team_id)


def get_by_name(db: Session, name: str) -> Team | None:
    """Fetch one team by its unique name."""
    return db.query(Team).filter(Team.name == name).first()


def list_teams(
    db: Session, league_id: int | None, limit: int, offset: int
) -> tuple[list[Team], int]:
    """Return one page of teams (optionally filtered by league) and the total count."""
    q = db.query(Team)
    if league_id is not None:
        q = q.filter(Team.league_id == league_id)
    total = q.count()
    rows = q.order_by(Team.id).offset(offset).limit(limit).all()
    return rows, total


def create(db: Session, payload: TeamCreate) -> Team:
    """Insert a new team."""
    team = Team(**payload.model_dump())
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


def update(db: Session, team: Team, payload: TeamUpdate) -> Team:
    """Apply only the fields that were sent in `payload`."""
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(team, field, value)
    db.commit()
    db.refresh(team)
    return team


def delete(db: Session, team: Team) -> None:
    """Delete a team."""
    db.delete(team)
    db.commit()

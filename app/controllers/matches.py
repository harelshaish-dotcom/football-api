"""Database operations for matches."""

from sqlalchemy.orm import Session

from app.models.match import Match
from app.schemas.match import MatchCreate, MatchUpdate


def get_by_id(db: Session, match_id: int) -> Match | None:
    """Fetch one match by primary key."""
    return db.get(Match, match_id)


def list_matches(
    db: Session, status: str | None, team_id: int | None, limit: int, offset: int
) -> tuple[list[Match], int]:
    """Return one page of matches, newest kickoff first, and the total count.

    `team_id` matches either the home or the away side.
    """
    q = db.query(Match)

    if status is not None:
        q = q.filter(Match.status == status)
    if team_id is not None:
        q = q.filter((Match.home_team_id == team_id) | (Match.away_team_id == team_id))

    total = q.count()
    rows = q.order_by(Match.kickoff_time.desc(), Match.id.desc()).offset(offset).limit(limit).all()
    return rows, total


def create(db: Session, payload: MatchCreate) -> Match:
    """Insert a new match."""
    match = Match(**payload.model_dump())
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


def update(db: Session, match: Match, payload: MatchUpdate) -> Match:
    """Apply only the fields that were sent in `payload`."""
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(match, field, value)
    db.commit()
    db.refresh(match)
    return match


def delete(db: Session, match: Match) -> None:
    """Delete a match."""
    db.delete(match)
    db.commit()

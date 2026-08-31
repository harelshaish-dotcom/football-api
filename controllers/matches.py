from sqlalchemy.orm import Session

from models.match import Match
from schemas.match import MatchCreate, MatchUpdate


def get_by_id(db: Session, match_id: int) -> Match | None:
    return db.get(Match, match_id)


def list_matches(db: Session, status: str | None, team_id: int | None, limit: int, offset: int):
    q = db.query(Match)

    if status is not None:
        q = q.filter(Match.status == status)
    if team_id is not None:
        q = q.filter((Match.home_team_id == team_id) | (Match.away_team_id == team_id))

    total = q.count()
    rows = q.order_by(Match.kickoff_time.desc(), Match.id.desc()).offset(offset).limit(limit).all()
    return rows, total


def create(db: Session, payload: MatchCreate) -> Match:
    match = Match(**payload.model_dump())
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


def update(db: Session, match: Match, payload: MatchUpdate) -> Match:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(match, field, value)
    db.commit()
    db.refresh(match)
    return match


def delete(db: Session, match: Match) -> None:
    db.delete(match)
    db.commit()

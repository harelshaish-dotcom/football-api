from sqlalchemy.orm import Session

from models.league import League
from schemas.league import LeagueCreate, LeagueUpdate


def get_by_id(db: Session, league_id: int) -> League | None:
    return db.get(League, league_id)


def get_by_name(db: Session, name: str) -> League | None:
    return db.query(League).filter(League.name == name).first()


def list_leagues(db: Session, country: str | None, limit: int, offset: int):
    q = db.query(League)
    if country is not None:
        q = q.filter(League.country == country)
    total = q.count()
    rows = q.order_by(League.league_id).offset(offset).limit(limit).all()
    return rows, total


def create(db: Session, payload: LeagueCreate) -> League:
    league = League(**payload.model_dump())
    db.add(league)
    db.commit()
    db.refresh(league)
    return league


def update(db: Session, league: League, payload: LeagueUpdate) -> League:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(league, field, value)
    db.commit()
    db.refresh(league)
    return league


def delete(db: Session, league: League) -> None:
    db.delete(league)
    db.commit()
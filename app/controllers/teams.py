"""Database operations for teams."""

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.match import Match
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


def get_standings(
    db: Session, *, league_id: int | None = None, team_id: int | None = None
) -> list[dict]:
    """W/D/L/GF/GA/GD/points per team, computed from finished matches.
    Filter by league_id (all teams in a league) or team_id (one team)."""
    is_home = Match.home_team_id == Team.id
    is_away = Match.away_team_id == Team.id
    home_win = Match.home_score > Match.away_score
    away_win = Match.away_score > Match.home_score
    draw = Match.home_score == Match.away_score

    goals_for = func.coalesce(
        func.sum(case((is_home, Match.home_score), (is_away, Match.away_score), else_=0)), 0
    )
    goals_against = func.coalesce(
        func.sum(case((is_home, Match.away_score), (is_away, Match.home_score), else_=0)), 0
    )
    points = func.coalesce(
        func.sum(
            case(
                (is_home & home_win, 3),
                (is_away & away_win, 3),
                (is_home & draw, 1),
                (is_away & draw, 1),
                else_=0,
            )
        ),
        0,
    )

    query = db.query(
        Team.id,
        Team.name,
        func.count(case((Match.status == "finished", Match.id))).label("played"),
        func.sum(case((is_home & home_win, 1), (is_away & away_win, 1), else_=0)).label("wins"),
        func.sum(case((is_home & draw, 1), (is_away & draw, 1), else_=0)).label("draws"),
        func.sum(
            case(
                (is_home & (Match.home_score < Match.away_score), 1),
                (is_away & (Match.away_score < Match.home_score), 1),
                else_=0,
            )
        ).label("losses"),
        goals_for.label("goals_for"),
        goals_against.label("goals_against"),
        (goals_for - goals_against).label("goal_difference"),
        points.label("points"),
    ).outerjoin(Match, is_home | is_away)

    if league_id is not None:
        query = query.filter(Team.league_id == league_id)
    if team_id is not None:
        query = query.filter(Team.id == team_id)

    rows = query.group_by(Team.id, Team.name).order_by(points.desc()).all()
    return [dict(row._mapping) for row in rows]

import time

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.controllers import leagues as leagues_ctl
from app.core.cache import get_cached, set_cached
from app.core.deps import api_rate_limit, get_current_admin
from app.core.responses import RATE_LIMITED, errors
from app.db.postgres import get_db
from app.models import Match, Team
from app.models.user import User
from app.schemas.league import LeagueCreate, LeagueOut, LeagueUpdate

router = APIRouter(
    prefix="/leagues",
    tags=["leagues"],
    dependencies=[Depends(api_rate_limit)],
    responses=RATE_LIMITED,
)

# Building blocks for the league table: "this team played at home / away"
_is_home = Match.home_team_id == Team.id
_is_away = Match.away_team_id == Team.id
_home_win = Match.home_score > Match.away_score
_away_win = Match.away_score > Match.home_score
_draw = Match.home_score == Match.away_score


@router.post(
    "",
    status_code=201,
    response_model=LeagueOut,
    responses=errors(401, 403, (409, "A league with that name already exists")),
)
def create_league(
    payload: LeagueCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Create a league (admin only). Names must be unique."""
    if leagues_ctl.get_by_name(db, payload.name):
        raise HTTPException(409, "A league with that name already exists")
    return leagues_ctl.create(db, payload)


@router.get("")
def list_leagues(
    country: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List leagues, optionally filtered by country."""
    rows, total = leagues_ctl.list_leagues(db, country, limit, offset)
    return {
        "items": [LeagueOut.model_validate(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{league_id}/table")
async def get_league_table(league_id: int, db: Session = Depends(get_db)):
    """League standings (played, W/D/L, goals, points). Cached for 5 minutes."""
    cache_key = f"league_table:{league_id}"
    cached_result = await get_cached(cache_key)

    if cached_result:
        cached_result["_cache"] = "HIT"
        return cached_result

    # Cache miss - compute standings
    start_time = time.time()

    points = func.coalesce(
        func.sum(
            case(
                (_is_home & _home_win, 3),
                (_is_away & _away_win, 3),
                (_is_home & _draw, 1),
                (_is_away & _draw, 1),
                else_=0,
            )
        ),
        0,
    )

    standings = (
        db.query(
            Team.name,
            func.count(case((Match.status == "finished", Match.id))).label("played"),
            func.sum(case((_is_home & _home_win, 1), (_is_away & _away_win, 1), else_=0)).label(
                "won"
            ),
            func.sum(case((_is_home & _draw, 1), (_is_away & _draw, 1), else_=0)).label("drawn"),
            func.sum(
                case(
                    (_is_home & (Match.home_score < Match.away_score), 1),
                    (_is_away & (Match.away_score < Match.home_score), 1),
                    else_=0,
                )
            ).label("lost"),
            func.coalesce(
                func.sum(case((_is_home, Match.home_score), (_is_away, Match.away_score), else_=0)),
                0,
            ).label("goals_for"),
            func.coalesce(
                func.sum(case((_is_home, Match.away_score), (_is_away, Match.home_score), else_=0)),
                0,
            ).label("goals_against"),
            points.label("points"),
        )
        .join(Team.league)
        .outerjoin(Match, _is_home | _is_away)
        .filter(Team.league_id == league_id)
        .group_by(Team.id, Team.name)
        .order_by(points.desc())
        .all()
    )

    elapsed = time.time() - start_time

    result = {
        "standings": [dict(row._mapping) for row in standings],
        "_timing_ms": round(elapsed * 1000, 2),
        "_cache": "MISS",
    }

    await set_cached(cache_key, result, ttl=300)

    return result


@router.get("/{league_id}", response_model=LeagueOut, responses=errors((404, "League not found")))
def get_league(league_id: int, db: Session = Depends(get_db)):
    """Get one league."""
    league = leagues_ctl.get_by_id(db, league_id)
    if not league:
        raise HTTPException(404, "League not found")
    return league


@router.patch(
    "/{league_id}",
    response_model=LeagueOut,
    responses=errors(
        401, 403, (404, "League not found"), (409, "A league with that name already exists")
    ),
)
def update_league(
    league_id: int,
    payload: LeagueUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Update some fields of a league (admin only)."""
    league = leagues_ctl.get_by_id(db, league_id)
    if not league:
        raise HTTPException(404, "League not found")
    if payload.name is not None:
        other = leagues_ctl.get_by_name(db, payload.name)
        if other and other.id != league_id:
            raise HTTPException(409, "A league with that name already exists")
    return leagues_ctl.update(db, league, payload)


@router.delete(
    "/{league_id}",
    status_code=204,
    responses=errors(401, 403, (404, "League not found"), (409, "League still has teams")),
)
def delete_league(
    league_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Delete a league (admin only)."""
    league = leagues_ctl.get_by_id(db, league_id)
    if not league:
        raise HTTPException(404, "League not found")
    teams = db.query(Team).filter(Team.league_id == league_id).count()
    if teams:
        raise HTTPException(409, f"League still has {teams} team(s); delete or move them first")
    leagues_ctl.delete(db, league)
    return Response(status_code=204)

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from database.postgres import get_db
from schemas.league import LeagueCreate, LeagueUpdate, LeagueOut
import controllers.leagues as leagues_ctl
from sqlalchemy import func, case
from models import League, Team, Match
from core.cache import get_cached, set_cached
import time

router = APIRouter(prefix="/leagues", tags=["leagues"])


@router.post("", status_code=201, response_model=LeagueOut)
def create_league(payload: LeagueCreate, db: Session = Depends(get_db)):
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
    rows, total = leagues_ctl.list_leagues(db, country, limit, offset)
    return {
        "items": [LeagueOut.model_validate(r) for r in rows],
        "total": total, "limit": limit, "offset": offset,
    }

@router.get("/{league_id}/table")
def get_league_table(league_id: int, db: Session = Depends(get_db)):
    import asyncio
    
    # Try to get from cache
    cache_key = f"league_table:{league_id}"
    cached_result = asyncio.run(get_cached(cache_key))
    
    if cached_result:
        cached_result["_cache"] = "HIT"
        return cached_result
    
    # Cache miss - compute standings
    start_time = time.time()
    
    standings = (
        db.query(
            Team.name,
            func.count(
                case(
                    (Match.status == "finished", Match.id)
                )
            ).label("played"),
            func.sum(
                case(
                    ((Match.home_team_id == Team.id) & (Match.home_score > Match.away_score), 1),
                    ((Match.away_team_id == Team.id) & (Match.away_score > Match.home_score), 1),
                    else_=0
                )
            ).label("won"),
            func.sum(
                case(
                    ((Match.home_team_id == Team.id) & (Match.home_score == Match.away_score), 1),
                    ((Match.away_team_id == Team.id) & (Match.away_score == Match.home_score), 1),
                    else_=0
                )
            ).label("drawn"),
            func.sum(
                case(
                    ((Match.home_team_id == Team.id) & (Match.home_score < Match.away_score), 1),
                    ((Match.away_team_id == Team.id) & (Match.away_score < Match.home_score), 1),
                    else_=0
                )
            ).label("lost"),
            func.coalesce(func.sum(case(((Match.home_team_id == Team.id), Match.home_score), ((Match.away_team_id == Team.id), Match.away_score), else_=0)), 0).label("goals_for"),
            func.coalesce(func.sum(case(((Match.home_team_id == Team.id), Match.away_score), ((Match.away_team_id == Team.id), Match.home_score), else_=0)), 0).label("goals_against"),
            func.coalesce(func.sum(case(((Match.home_team_id == Team.id) & (Match.home_score > Match.away_score), 3), ((Match.away_team_id == Team.id) & (Match.away_score > Match.home_score), 3), ((Match.home_team_id == Team.id) & (Match.home_score == Match.away_score), 1), ((Match.away_team_id == Team.id) & (Match.away_score == Match.home_score), 1), else_=0)), 0).label("points"),
        )
        .join(Team.league)
        .outerjoin(Match, (Match.home_team_id == Team.id) | (Match.away_team_id == Team.id))
        .filter(Team.league_id == league_id)
        .group_by(Team.id, Team.name)
        .order_by(func.coalesce(func.sum(case(((Match.home_team_id == Team.id) & (Match.home_score > Match.away_score), 3), ((Match.away_team_id == Team.id) & (Match.away_score > Match.home_score), 3), ((Match.home_team_id == Team.id) & (Match.home_score == Match.away_score), 1), ((Match.away_team_id == Team.id) & (Match.away_score == Match.home_score), 1), else_=0)), 0).desc())
        .all()
    )
    
    elapsed = time.time() - start_time
    
    result = {
        "standings": [dict(row._mapping) for row in standings],
        "_timing_ms": round(elapsed * 1000, 2),
        "_cache": "MISS"
    }
    
    # Cache for 5 minutes (300 seconds)
    asyncio.run(set_cached(cache_key, result, ttl=300))
    
    return result

@router.get("/{league_id}", response_model=LeagueOut)
def get_league(league_id: int, db: Session = Depends(get_db)):
    league = leagues_ctl.get_by_id(db, league_id)
    if not league:
        raise HTTPException(404, "League not found")
    return league


@router.patch("/{league_id}", response_model=LeagueOut)
def update_league(league_id: int, payload: LeagueUpdate,
                  db: Session = Depends(get_db)):
    league = leagues_ctl.get_by_id(db, league_id)
    if not league:
        raise HTTPException(404, "League not found")
    return leagues_ctl.update(db, league, payload)


@router.delete("/{league_id}", status_code=204)
def delete_league(league_id: int, db: Session = Depends(get_db)):
    league = leagues_ctl.get_by_id(db, league_id)
    if not league:
        raise HTTPException(404, "League not found")
    leagues_ctl.delete(db, league)
    return Response(status_code=204)
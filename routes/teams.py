from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from database.connection import get_db
from schemas.team import TeamCreate, TeamUpdate, TeamOut
import controllers.teams as teams_ctl
import controllers.players as player_ctl
from core.deps import get_current_admin
from models import Team
from schemas.players import PlayerOut
from sqlalchemy.orm import Session, selectinload
from core.cache import get_cached, set_cached, delete_cached
from models.user import User
import time


router = APIRouter(prefix="/teams", tags=["teams"])


@router.post("", status_code=201, response_model=TeamOut)
def create_team(payload: TeamCreate, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    if teams_ctl.get_by_name(db, payload.name):
        raise HTTPException(409, "A team with that name already exists")
    return teams_ctl.create(db, payload)

@router.get("/{team_id}", response_model=TeamOut)
def get_team(team_id: int, db: Session = Depends(get_db)):
    import asyncio
    
    # Try to get from cache
    cache_key = f"team:{team_id}"
    cached_result = asyncio.run(get_cached(cache_key))
    
    if cached_result:
        cached_result["_cache"] = "HIT"
        return cached_result
    
    # Cache miss - fetch from DB
    start_time = time.time()
    team = teams_ctl.get_by_id(db, team_id)
    if not team:
        raise HTTPException(404, "Team not found")
    
    elapsed = time.time() - start_time
    
    result = TeamOut.model_validate(team).model_dump()
    result["_timing_ms"] = round(elapsed * 1000, 2)
    result["_cache"] = "MISS"
    
    # Cache for 60 seconds
    asyncio.run(set_cached(cache_key, result, ttl=60))
    
    return result

@router.get("/")
def get_teams(
    league_id: int | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    import asyncio
    
    # Build cache key including pagination and filtering params
    cache_key = f"teams_list:league={league_id}:limit={limit}:offset={offset}"
    cached_result = asyncio.run(get_cached(cache_key))
    
    if cached_result:
        cached_result["_cache"] = "HIT"
        return cached_result
    
    # Cache miss - fetch from DB
    start_time = time.time()
    
    query = db.query(Team).options(selectinload(Team.players))
    if league_id is not None:
        query = query.filter(Team.league_id == league_id)
    
    total = query.count()
    teams = query.limit(limit).offset(offset).all()
    
    elapsed = time.time() - start_time
    
    result = {
        "teams": [
            {
                "id": t.id,
                "name": t.name,
                "player_count": len(t.players)
            }
            for t in teams
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
        "_timing_ms": round(elapsed * 1000, 2),
        "_cache": "MISS"
    }
    
    # Cache for 5 minutes
    asyncio.run(set_cached(cache_key, result, ttl=300))
    
    return result

@router.get("/{team_id}/players", response_model=list[PlayerOut])
def get_team_players(team_id: int, db: Session = Depends(get_db)):
    team = teams_ctl.get_by_id(db, team_id)
    if not team:
        raise HTTPException(404, "Team not found")
        
    players, total = player_ctl.list_players_club(db, team_id, limit=100, offset=0)
    return players

@router.patch("/{team_id}", response_model=TeamOut)
def update_team(team_id: int, payload: TeamUpdate,
                db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    import asyncio
    
    team = teams_ctl.get_by_id(db, team_id)
    if not team:
        raise HTTPException(404, "Team not found")
    
    result = teams_ctl.update(db, team, payload)
    
    # Invalidate cache
    cache_key = f"team:{team_id}"
    asyncio.run(delete_cached(cache_key))
    
    return result


@router.delete("/{team_id}", status_code=204)
def delete_team(team_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    import asyncio
    
    team = teams_ctl.get_by_id(db, team_id)
    if not team:
        raise HTTPException(404, "Team not found")
    
    teams_ctl.delete(db, team)
    
    # Invalidate cache
    cache_key = f"team:{team_id}"
    asyncio.run(delete_cached(cache_key))
    
    return Response(status_code=204)
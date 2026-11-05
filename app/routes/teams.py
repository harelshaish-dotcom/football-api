import time

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session, selectinload

from app.controllers import players as players_ctl
from app.controllers import teams as teams_ctl
from app.core.cache import (
    delete_by_pattern,
    delete_cached,
    forget_team_views,
    get_cached,
    get_popular_teams,
    get_views,
    increment_views,
    set_cached,
)
from app.core.deps import api_rate_limit, get_current_admin
from app.core.responses import RATE_LIMITED, errors
from app.db.postgres import get_db
from app.models import League, Match, Player, Team
from app.models.user import User
from app.schemas.player import PlayerOut
from app.schemas.team import TeamCreate, TeamOut, TeamUpdate

router = APIRouter(
    prefix="/teams",
    tags=["teams"],
    dependencies=[Depends(api_rate_limit)],
    responses=RATE_LIMITED,
)


def _require_league(db: Session, league_id: int) -> None:
    """404 if the league a team should belong to doesn't exist (instead of an FK error)."""
    if not db.get(League, league_id):
        raise HTTPException(404, f"League {league_id} not found")


async def _invalidate_team_caches(team_id: int | None, *league_ids: int) -> None:
    """Clear every cached response that shows this team's data.

    - team:{id}            the single team
    - teams_list:*         every cached page of the team list
    - league_table:{id}    standings of the league(s) the team is or was in
    """
    if team_id is not None:
        await delete_cached(f"team:{team_id}")
    await delete_by_pattern("teams_list:*")
    for league_id in set(league_ids):
        await delete_cached(f"league_table:{league_id}")


@router.post(
    "",
    status_code=201,
    response_model=TeamOut,
    responses=errors(
        401, 403, (404, "League not found"), (409, "A team with that name already exists")
    ),
)
async def create_team(
    payload: TeamCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Create a team (admin only). Names must be unique."""
    if teams_ctl.get_by_name(db, payload.name):
        raise HTTPException(409, "A team with that name already exists")
    _require_league(db, payload.league_id)
    team = teams_ctl.create(db, payload)

    await _invalidate_team_caches(None, team.league_id)

    return team


# Must be declared before /{team_id}, or "popular" would be parsed as a team_id (422).
@router.get("/popular")
async def get_popular(db: Session = Depends(get_db)):
    """The 10 most viewed teams, most viewed first."""
    ranking = await get_popular_teams(limit=10)
    if not ranking:
        return []

    # One query for all names; IDs of teams that no longer exist are skipped.
    ids = [team_id for team_id, _ in ranking]
    names = dict(db.query(Team.id, Team.name).filter(Team.id.in_(ids)).all())

    result = []
    for team_id, views in ranking:
        if team_id in names:
            result.append(
                {
                    "team_id": team_id,
                    "name": names[team_id],
                    "views": views,
                    "rank": len(result) + 1,
                }
            )
    return result


@router.get("/{team_id}", response_model=TeamOut, responses=errors((404, "Team not found")))
async def get_team(team_id: int, db: Session = Depends(get_db)):
    """Get one team. Cached for 60 seconds. Every successful call counts as a view."""
    cache_key = f"team:{team_id}"
    cached_result = await get_cached(cache_key)

    if cached_result:
        await increment_views(team_id)
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

    await set_cached(cache_key, result, ttl=60)
    await increment_views(team_id)

    return result


@router.get("/{team_id}/views", responses=errors((404, "Team not found")))
async def get_team_views(team_id: int, db: Session = Depends(get_db)):
    """How many times GET /teams/{team_id} has succeeded for this team."""
    if not teams_ctl.get_by_id(db, team_id):
        raise HTTPException(404, "Team not found")
    return {"team_id": team_id, "views": await get_views(team_id)}


@router.get("/")
async def get_teams(
    league_id: int | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List teams with their player counts. Cached for 5 minutes per page."""
    cache_key = f"teams_list:league={league_id}:limit={limit}:offset={offset}"
    cached_result = await get_cached(cache_key)

    if cached_result:
        cached_result["_cache"] = "HIT"
        return cached_result

    # Cache miss - fetch from DB (selectinload avoids one query per team)
    start_time = time.time()

    query = db.query(Team).options(selectinload(Team.players))
    if league_id is not None:
        query = query.filter(Team.league_id == league_id)

    total = query.count()
    teams = query.limit(limit).offset(offset).all()

    elapsed = time.time() - start_time

    result = {
        "teams": [{"id": t.id, "name": t.name, "player_count": len(t.players)} for t in teams],
        "total": total,
        "limit": limit,
        "offset": offset,
        "_timing_ms": round(elapsed * 1000, 2),
        "_cache": "MISS",
    }

    await set_cached(cache_key, result, ttl=300)

    return result


@router.get(
    "/{team_id}/players",
    response_model=list[PlayerOut],
    responses=errors((404, "Team not found")),
)
def get_team_players(team_id: int, db: Session = Depends(get_db)):
    """List up to 100 players of a team."""
    team = teams_ctl.get_by_id(db, team_id)
    if not team:
        raise HTTPException(404, "Team not found")

    players, _total = players_ctl.list_players(db, team_id, None, limit=100, offset=0)
    return players


@router.patch(
    "/{team_id}",
    response_model=TeamOut,
    responses=errors(
        401,
        403,
        (404, "Team or league not found"),
        (409, "A team with that name already exists"),
    ),
)
async def update_team(
    team_id: int,
    payload: TeamUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Update some fields of a team (admin only) and clear the caches that show it."""
    team = teams_ctl.get_by_id(db, team_id)
    if not team:
        raise HTTPException(404, "Team not found")

    if payload.league_id is not None:
        _require_league(db, payload.league_id)
    if payload.name is not None:
        other = teams_ctl.get_by_name(db, payload.name)
        if other and other.id != team_id:
            raise HTTPException(409, "A team with that name already exists")

    old_league_id = team.league_id
    result = teams_ctl.update(db, team, payload)

    # If the team moved league, both standings change.
    await _invalidate_team_caches(team_id, old_league_id, result.league_id)

    return result


@router.delete(
    "/{team_id}",
    status_code=204,
    responses=errors(401, 403, (404, "Team not found"), (409, "Team still has players or matches")),
)
async def delete_team(
    team_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Delete a team (admin only), clear the caches that show it and drop its view stats."""
    team = teams_ctl.get_by_id(db, team_id)
    if not team:
        raise HTTPException(404, "Team not found")

    players = db.query(Player).filter(Player.team_id == team_id).count()
    matches = (
        db.query(Match)
        .filter((Match.home_team_id == team_id) | (Match.away_team_id == team_id))
        .count()
    )
    if players or matches:
        raise HTTPException(
            409,
            f"Team still has {players} player(s) and {matches} match(es); "
            "delete or move them first",
        )

    league_id = team.league_id
    teams_ctl.delete(db, team)

    await _invalidate_team_caches(team_id, league_id)
    await forget_team_views(team_id)

    return Response(status_code=204)

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.controllers import players as players_ctl
from app.core.deps import api_rate_limit, get_current_admin
from app.core.responses import RATE_LIMITED, errors
from app.db.postgres import get_db
from app.models import Team
from app.models.user import User
from app.schemas.player import PlayerCreate, PlayerOut, PlayerUpdate

router = APIRouter(
    prefix="/players",
    tags=["players"],
    dependencies=[Depends(api_rate_limit)],
    responses=RATE_LIMITED,
)


def _require_team(db: Session, team_id: int) -> None:
    """404 if the team a player should belong to doesn't exist (instead of an FK error)."""
    if not db.get(Team, team_id):
        raise HTTPException(404, f"Team {team_id} not found")


@router.post(
    "",
    status_code=201,
    response_model=PlayerOut,
    responses=errors(401, 403, (404, "Team not found")),
)
def create_player(
    payload: PlayerCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Create a player (admin only)."""
    _require_team(db, payload.team_id)
    return players_ctl.create(db, payload)


@router.get("")
def list_players(
    team_id: int | None = None,
    country: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List players, optionally filtered by team and country."""
    rows, total = players_ctl.list_players(db, team_id, country, limit, offset)
    return {
        "items": [PlayerOut.model_validate(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{player_id}", response_model=PlayerOut, responses=errors((404, "Player not found")))
def get_player(player_id: int, db: Session = Depends(get_db)):
    """Get one player."""
    player = players_ctl.get_by_id(db, player_id)
    if not player:
        raise HTTPException(404, "Player not found")
    return player


@router.patch(
    "/{player_id}",
    response_model=PlayerOut,
    responses=errors(401, 403, (404, "Player or team not found")),
)
def update_player(
    player_id: int,
    payload: PlayerUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Update some fields of a player (admin only)."""
    player = players_ctl.get_by_id(db, player_id)
    if not player:
        raise HTTPException(404, "Player not found")
    if payload.team_id is not None:
        _require_team(db, payload.team_id)
    return players_ctl.update(db, player, payload)


@router.delete(
    "/{player_id}", status_code=204, responses=errors(401, 403, (404, "Player not found"))
)
def delete_player(
    player_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Delete a player (admin only)."""
    player = players_ctl.get_by_id(db, player_id)
    if not player:
        raise HTTPException(404, "Player not found")
    players_ctl.delete(db, player)
    return Response(status_code=204)

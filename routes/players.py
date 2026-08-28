from fastapi import APIRouter, Depends, HTTPException, Query, Response
from database.connection import get_db
from schemas.players import PlayerCreate, PlayerUpdate, PlayerOut
import controllers.players as players_ctl
from core.deps import get_current_admin

router = APIRouter(prefix="/players", tags=["players"])


@router.post("", status_code=201, response_model=PlayerOut)
def create_player(payload: PlayerCreate, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    return players_ctl.create(db, payload)


@router.get("")
def list_players(
    team_id: int | None = None,
    country: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    rows, total = players_ctl.list_players(db, team_id, country, limit, offset)
    return {
        "items": [PlayerOut.model_validate(r) for r in rows],
        "total": total, "limit": limit, "offset": offset,
    }


@router.get("/{player_id}", response_model=PlayerOut)
def get_player(player_id: int, db: Session = Depends(get_db)):
    player = players_ctl.get_by_id(db, player_id)
    if not player:
        raise HTTPException(404, "Player not found")
    return player


@router.patch("/{player_id}", response_model=PlayerOut)
def update_player(player_id: int, payload: PlayerUpdate,
                  db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    player = players_ctl.get_by_id(db, player_id)
    if not player:
        raise HTTPException(404, "Player not found")
    return players_ctl.update(db, player, payload)


@router.delete("/{player_id}", status_code=204)
def delete_player(player_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    player = players_ctl.get_by_id(db, player_id)
    if not player:
        raise HTTPException(404, "Player not found")
    players_ctl.delete(db, player)
    return Response(status_code=204)
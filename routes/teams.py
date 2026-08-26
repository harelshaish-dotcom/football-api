from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from database.connection import get_db
from schemas.team import TeamCreate, TeamUpdate, TeamOut
import controllers.teams as teams_ctl

router = APIRouter(prefix="/teams", tags=["teams"])


@router.post("", status_code=201, response_model=TeamOut)
def create_team(payload: TeamCreate, db: Session = Depends(get_db)):
    if teams_ctl.get_by_name(db, payload.name):
        raise HTTPException(409, "A team with that name already exists")
    return teams_ctl.create(db, payload)


@router.get("")
def list_teams(
    league_id: int | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    rows, total = teams_ctl.list_teams(db, league_id, limit, offset)
    return {
        "items": [TeamOut.model_validate(r) for r in rows],
        "total": total, "limit": limit, "offset": offset,
    }


@router.get("/{team_id}", response_model=TeamOut)
def get_team(team_id: int, db: Session = Depends(get_db)):
    team = teams_ctl.get_by_id(db, team_id)
    if not team:
        raise HTTPException(404, "Team not found")
    return team


@router.patch("/{team_id}", response_model=TeamOut)
def update_team(team_id: int, payload: TeamUpdate,
                db: Session = Depends(get_db)):
    team = teams_ctl.get_by_id(db, team_id)
    if not team:
        raise HTTPException(404, "Team not found")
    return teams_ctl.update(db, team, payload)


@router.delete("/{team_id}", status_code=204)
def delete_team(team_id: int, db: Session = Depends(get_db)):
    team = teams_ctl.get_by_id(db, team_id)
    if not team:
        raise HTTPException(404, "Team not found")
    teams_ctl.delete(db, team)
    return Response(status_code=204)
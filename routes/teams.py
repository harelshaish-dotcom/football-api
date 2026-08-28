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


router = APIRouter(prefix="/teams", tags=["teams"])


@router.post("", status_code=201, response_model=TeamOut)
def create_team(payload: TeamCreate, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    if teams_ctl.get_by_name(db, payload.name):
        raise HTTPException(409, "A team with that name already exists")
    return teams_ctl.create(db, payload)

@router.get("/{team_id}", response_model=TeamOut)
def get_team(team_id: int, db: Session = Depends(get_db)):
    team = teams_ctl.get_by_id(db, team_id)
    if not team:
        raise HTTPException(404, "Team not found")
    return team

@router.get("/")
def get_teams(db: Session = Depends(get_db)):
    teams = db.query(Team).options(selectinload(Team.players)).all()
    
    return {
        "teams": [
            {
                "id": t.id,
                "name": t.name,
                "player_count": len(t.players)
            }
            for t in teams
        ]
    }

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
    team = teams_ctl.get_by_id(db, team_id)
    if not team:
        raise HTTPException(404, "Team not found")
    return teams_ctl.update(db, team, payload)


@router.delete("/{team_id}", status_code=204)
def delete_team(team_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    team = teams_ctl.get_by_id(db, team_id)
    if not team:
        raise HTTPException(404, "Team not found")
    teams_ctl.delete(db, team)
    return Response(status_code=204)
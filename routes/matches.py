from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from database.mongo import events
from controllers import matches as matches_ctl
from core.deps import get_current_admin
from database.postgres import get_db
from models import Team, User
from schemas.match import MatchCreate, MatchOut, MatchUpdate
from schemas.events import EventCreate

router = APIRouter(prefix="/matches", tags=["matches"])


@router.post("", status_code=201, response_model=MatchOut)
def create_match(
    payload: MatchCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    if payload.home_team_id == payload.away_team_id:
        raise HTTPException(400, "Home and away teams must be different")
    if not db.get(Team, payload.home_team_id):
        raise HTTPException(404, "Home team not found")
    if not db.get(Team, payload.away_team_id):
        raise HTTPException(404, "Away team not found")

    return matches_ctl.create(db, payload)


@router.get("")
def list_matches(
    status: str | None = None,
    team_id: int | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    rows, total = matches_ctl.list_matches(db, status, team_id, limit, offset)
    return {
        "items": [MatchOut.model_validate(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{match_id}", response_model=MatchOut)
def get_match(match_id: int, db: Session = Depends(get_db)):
    match = matches_ctl.get_by_id(db, match_id)
    if not match:
        raise HTTPException(404, "Match not found")
    return match

@router.get("/{match_id}/events")
async def get_match_events(match_id: int, db: Session = Depends(get_db), skip: int = 0, limit: int = 50, type: str | None = None,):
    match = matches_ctl.get_by_id(db, match_id)
    if not match:
        raise HTTPException(404, "Match not found")
    filter = {"match_id": match_id}
    if type is not None:
        filter["type"] = type
    cursor = events.find(filter).sort("minute", 1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    for doc in docs:
        doc["id"] = str(doc["_id"])
        doc.pop("_id", None)

        

    return docs

@router.post("/{match_id}/events", status_code=201)
async def create_match_event(match_id: int, payload: EventCreate, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    match = matches_ctl.get_by_id(db, match_id)
    if not match:
        raise HTTPException(404, "Match not found")
    doc = payload.model_dump()
    doc["match_id"] = match_id
    result = await events.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)
    await publish("match-events", key=str(match_id), value={
        "event_id": doc["id"],
        "match_id": match_id,
        "type": payload.type,
        "player_id": payload.player.id,
        "minute": payload.minute,
    })
    return doc


@router.get("/{match_id}/timeline")
async def get_match_timeline(match_id: int, db: Session = Depends(get_db)):
    match = matches_ctl.get_by_id(db, match_id)
    if not match:
        raise HTTPException(404, "Match not found")
    
    cursor = events.find({"match_id": match_id}).sort("minute", 1)
    events_list = await cursor.to_list(length=None)
    
    for doc in events_list:
        doc["id"] = str(doc["_id"])
        doc.pop("_id", None)
    
    return {
        "match": {
            "id": match.id,
            "home_team": {
                "id": match.home_team.id,
                "name": match.home_team.name
            },
            "away_team": {
                "id": match.away_team.id,
                "name": match.away_team.name
            },
            "kickoff_time": match.kickoff_time.isoformat(),
            "status": match.status,
            "home_score": match.home_score,
            "away_score": match.away_score
        },
        "events": events_list
    }



@router.patch("/{match_id}", response_model=MatchOut)
def update_match(
    match_id: int,
    payload: MatchUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    match = matches_ctl.get_by_id(db, match_id)
    if not match:
        raise HTTPException(404, "Match not found")

    final_home_team_id = payload.home_team_id if payload.home_team_id is not None else match.home_team_id
    final_away_team_id = payload.away_team_id if payload.away_team_id is not None else match.away_team_id

    if final_home_team_id == final_away_team_id:
        raise HTTPException(400, "Home and away teams must be different")
    if not db.get(Team, final_home_team_id):
        raise HTTPException(404, "Home team not found")
    if not db.get(Team, final_away_team_id):
        raise HTTPException(404, "Away team not found")

    return matches_ctl.update(db, match, payload)


@router.delete("/{match_id}", status_code=204)
def delete_match(
    match_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    match = matches_ctl.get_by_id(db, match_id)
    if not match:
        raise HTTPException(404, "Match not found")
    matches_ctl.delete(db, match)
    return Response(status_code=204)

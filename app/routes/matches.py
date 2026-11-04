import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.controllers import matches as matches_ctl
from app.core.deps import get_current_admin
from app.core.events import publish
from app.db.mongo import events
from app.db.postgres import get_db
from app.models import Team, User
from app.schemas.event import EventCreate
from app.schemas.match import MatchCreate, MatchOut, MatchUpdate

router = APIRouter(prefix="/matches", tags=["matches"])


def _serialize(doc: dict) -> dict:
    """Replace Mongo's ObjectId `_id` with a string `id`."""
    doc["id"] = str(doc["_id"])
    doc.pop("_id", None)
    return doc


@router.post("", status_code=201, response_model=MatchOut)
def create_match(
    payload: MatchCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Create a match (admin only)."""
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
    """List matches, newest first, optionally filtered by status or team."""
    rows, total = matches_ctl.list_matches(db, status, team_id, limit, offset)
    return {
        "items": [MatchOut.model_validate(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{match_id}", response_model=MatchOut)
def get_match(match_id: int, db: Session = Depends(get_db)):
    """Get one match."""
    match = matches_ctl.get_by_id(db, match_id)
    if not match:
        raise HTTPException(404, "Match not found")
    return match


@router.get("/{match_id}/events")
async def get_match_events(
    match_id: int,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 50,
    type: str | None = None,
):
    """List a match's events in minute order, optionally filtered by type."""
    match = matches_ctl.get_by_id(db, match_id)
    if not match:
        raise HTTPException(404, "Match not found")
    query = {"match_id": match_id}
    if type is not None:
        query["type"] = type
    cursor = events.find(query).sort("minute", 1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_serialize(doc) for doc in docs]


@router.post("/{match_id}/events", status_code=201)
async def create_match_event(
    match_id: int,
    payload: EventCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Record an event (admin only), store it in MongoDB and publish it to Kafka."""
    match = matches_ctl.get_by_id(db, match_id)
    if not match:
        raise HTTPException(404, "Match not found")

    doc = payload.model_dump()
    doc["match_id"] = match_id
    result = await events.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)

    try:
        await publish(
            "match-events",
            key=str(match_id),
            value={
                "event_id": doc["id"],
                "match_id": match_id,
                "type": payload.type,
                "player_id": payload.player.id,
                "minute": payload.minute,
            },
        )
    except Exception as e:
        logging.error("publish failed: %s", e)

    return doc


@router.get("/{match_id}/timeline")
async def get_match_timeline(match_id: int, db: Session = Depends(get_db)):
    """A match's details plus all of its events in minute order."""
    match = matches_ctl.get_by_id(db, match_id)
    if not match:
        raise HTTPException(404, "Match not found")

    cursor = events.find({"match_id": match_id}).sort("minute", 1)
    events_list = [_serialize(doc) for doc in await cursor.to_list(length=None)]

    return {
        "match": {
            "id": match.id,
            "home_team": {"id": match.home_team.id, "name": match.home_team.name},
            "away_team": {"id": match.away_team.id, "name": match.away_team.name},
            "kickoff_time": match.kickoff_time.isoformat(),
            "status": match.status,
            "home_score": match.home_score,
            "away_score": match.away_score,
        },
        "events": events_list,
    }


@router.patch("/{match_id}", response_model=MatchOut)
def update_match(
    match_id: int,
    payload: MatchUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Update some fields of a match (admin only)."""
    match = matches_ctl.get_by_id(db, match_id)
    if not match:
        raise HTTPException(404, "Match not found")

    final_home_team_id = (
        payload.home_team_id if payload.home_team_id is not None else match.home_team_id
    )
    final_away_team_id = (
        payload.away_team_id if payload.away_team_id is not None else match.away_team_id
    )

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
    """Delete a match (admin only)."""
    match = matches_ctl.get_by_id(db, match_id)
    if not match:
        raise HTTPException(404, "Match not found")
    matches_ctl.delete(db, match)
    return Response(status_code=204)

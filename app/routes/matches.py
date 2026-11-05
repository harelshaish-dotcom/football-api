from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pymongo import ReturnDocument
from sqlalchemy.orm import Session

from app.controllers import matches as matches_ctl
from app.core.cache import rebuild_leaderboard
from app.core.deps import api_rate_limit, get_current_admin
from app.core.events import publish_match_event
from app.core.responses import RATE_LIMITED, errors
from app.db.mongo import events
from app.db.postgres import get_db
from app.models import Team, User
from app.schemas.event import EventCreate, EventUpdate, TagCreate
from app.schemas.match import MatchCreate, MatchOut, MatchUpdate

router = APIRouter(
    prefix="/matches",
    tags=["matches"],
    dependencies=[Depends(api_rate_limit)],
    responses=RATE_LIMITED,
)

_TEAMS_DIFFERENT = (400, "Home and away teams must be different")
_EVENT_404 = (404, "Match or event not found")


def _serialize(doc: dict) -> dict:
    """Replace Mongo's ObjectId `_id` with a string `id`."""
    doc["id"] = str(doc["_id"])
    doc.pop("_id", None)
    return doc


def _require_match(db: Session, match_id: int) -> None:
    """404 if the match doesn't exist in Postgres."""
    if not matches_ctl.get_by_id(db, match_id):
        raise HTTPException(404, "Match not found")


def _event_oid(event_id: str) -> ObjectId:
    """Convert an event id to an ObjectId, 404 if it isn't a valid one."""
    try:
        return ObjectId(event_id)
    except InvalidId:
        raise HTTPException(404, "Event not found") from None


@router.post(
    "",
    status_code=201,
    response_model=MatchOut,
    responses=errors(_TEAMS_DIFFERENT, 401, 403, (404, "Home or away team not found")),
)
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


@router.get("/{match_id}", response_model=MatchOut, responses=errors((404, "Match not found")))
def get_match(match_id: int, db: Session = Depends(get_db)):
    """Get one match."""
    match = matches_ctl.get_by_id(db, match_id)
    if not match:
        raise HTTPException(404, "Match not found")
    return match


@router.get("/{match_id}/events", responses=errors((404, "Match not found")))
async def get_match_events(
    match_id: int,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 50,
    type: str | None = None,
    player_id: int | None = None,
    tag: str | None = None,
):
    """List a match's events in minute order, optionally filtered by type, player or tag."""
    _require_match(db, match_id)
    query = {"match_id": match_id}
    if type is not None:
        query["type"] = type
    if player_id is not None:
        query["player.id"] = player_id
    if tag is not None:
        query["tags"] = tag  # matches if `tag` is any element of the array
    cursor = events.find(query).sort("minute", 1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_serialize(doc) for doc in docs]


@router.get("/{match_id}/events/{event_id}", responses=errors(_EVENT_404))
async def get_match_event(match_id: int, event_id: str, db: Session = Depends(get_db)):
    """Get one event of a match."""
    _require_match(db, match_id)
    doc = await events.find_one({"_id": _event_oid(event_id), "match_id": match_id})
    if doc is None:
        raise HTTPException(404, "Event not found")
    return _serialize(doc)


@router.post(
    "/{match_id}/events", status_code=201, responses=errors(401, 403, (404, "Match not found"))
)
async def create_match_event(
    match_id: int,
    payload: EventCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Record an event (admin only), store it in MongoDB and publish it to Kafka.

    Outbox pattern: the event is saved with published=false and flipped to true once
    Kafka acks. If Kafka is down the request still succeeds (the event is saved) and
    scripts/republish_events.py sends it later, so no event is silently lost.
    The workers (not this request) update the leaderboard and notify followers.
    """
    match = matches_ctl.get_by_id(db, match_id)
    if not match:
        raise HTTPException(404, "Match not found")

    doc = payload.model_dump()
    doc["match_id"] = match_id
    doc["published"] = False
    await events.insert_one(doc)  # sets doc["_id"]

    if await publish_match_event(doc):
        doc["published"] = True

    return _serialize(doc)


@router.patch(
    "/{match_id}/events/{event_id}",
    responses=errors((400, "No fields to update"), 401, 403, _EVENT_404),
)
async def update_match_event(
    match_id: int,
    event_id: str,
    payload: EventUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Update some fields of an event (admin only)."""
    _require_match(db, match_id)
    oid = _event_oid(event_id)

    # exclude_none: an explicit null shouldn't blank out a required field.
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    # Flatten the embedded player into dotted paths so a partial player
    # update ({"name": ...}) doesn't wipe the other player fields.
    player = changes.pop("player", None) or {}
    for field, value in player.items():
        changes[f"player.{field}"] = value
    if not changes:
        raise HTTPException(400, "No fields to update")

    doc = await events.find_one_and_update(
        {"_id": oid, "match_id": match_id},
        {"$set": changes},
        return_document=ReturnDocument.AFTER,
    )
    if doc is None:
        raise HTTPException(404, "Event not found")
    # Rebuild if the event is a goal now, or its type changed (it may have been one).
    if doc.get("type") == "goal" or "type" in changes:
        await rebuild_leaderboard()
    return _serialize(doc)


@router.delete(
    "/{match_id}/events/{event_id}", status_code=204, responses=errors(401, 403, _EVENT_404)
)
async def delete_match_event(
    match_id: int,
    event_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Delete an event (admin only)."""
    _require_match(db, match_id)
    doc = await events.find_one_and_delete({"_id": _event_oid(event_id), "match_id": match_id})
    if doc is None:
        raise HTTPException(404, "Event not found")
    if doc.get("type") == "goal":
        await rebuild_leaderboard()
    return Response(status_code=204)


@router.post(
    "/{match_id}/events/{event_id}/tags",
    status_code=201,
    responses=errors(401, 403, _EVENT_404),
)
async def add_event_tag(
    match_id: int,
    event_id: str,
    payload: TagCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Add a tag to an event (admin only). Adding a tag it already has is a no-op."""
    _require_match(db, match_id)
    doc = await events.find_one_and_update(
        {"_id": _event_oid(event_id), "match_id": match_id},
        {"$addToSet": {"tags": payload.tag}},
        return_document=ReturnDocument.AFTER,
    )
    if doc is None:
        raise HTTPException(404, "Event not found")
    return _serialize(doc)


@router.delete("/{match_id}/events/{event_id}/tags/{tag}", responses=errors(401, 403, _EVENT_404))
async def remove_event_tag(
    match_id: int,
    event_id: str,
    tag: str,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Remove every occurrence of a tag from an event (admin only)."""
    _require_match(db, match_id)
    doc = await events.find_one_and_update(
        {"_id": _event_oid(event_id), "match_id": match_id},
        {"$pull": {"tags": tag}},
        return_document=ReturnDocument.AFTER,
    )
    if doc is None:
        raise HTTPException(404, "Event not found")
    return _serialize(doc)


@router.get("/{match_id}/timeline", responses=errors((404, "Match not found")))
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


@router.patch(
    "/{match_id}",
    response_model=MatchOut,
    responses=errors(_TEAMS_DIFFERENT, 401, 403, (404, "Match, home or away team not found")),
)
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


@router.delete("/{match_id}", status_code=204, responses=errors(401, 403, (404, "Match not found")))
async def delete_match(
    match_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Delete a match and all of its events (admin only)."""
    match = matches_ctl.get_by_id(db, match_id)
    if not match:
        raise HTTPException(404, "Match not found")
    matches_ctl.delete(db, match)
    result = await events.delete_many({"match_id": match_id})
    if result.deleted_count:
        await rebuild_leaderboard()
    return Response(status_code=204)

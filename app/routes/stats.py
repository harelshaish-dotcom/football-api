from fastapi import APIRouter, Depends, Query

from app.core.deps import api_rate_limit
from app.core.responses import RATE_LIMITED
from app.db.mongo import events

router = APIRouter(
    prefix="/stats",
    tags=["stats"],
    dependencies=[Depends(api_rate_limit)],
    responses=RATE_LIMITED,
)


@router.get("/top-scorers")
async def get_top_scorers(league_id: int | None = None, limit: int = Query(10, ge=1, le=100)):
    """Get top scorers by goals scored.

    Returns the top N players by goal count, with optional league_id filter.
    Uses MongoDB aggregation pipeline to count goals from match events.

    - **limit**: Number of top scorers to return (1-100, default 10)
    - **league_id**: Optional league filter (not yet fully implemented - requires cross-db join)

    Example: GET /stats/top-scorers?limit=10
    """
    pipeline = [
        {"$match": {"type": "goal"}},
        {
            "$group": {
                "_id": "$player.id",
                "player_name": {"$first": "$player.name"},
                "goals": {"$sum": 1},
            }
        },
        {"$sort": {"goals": -1}},
        {"$limit": limit},
    ]

    cursor = events.aggregate(pipeline)
    top_scorers = await cursor.to_list(length=limit)

    # league_id is not applied yet: filtering would need the league's match IDs
    # from PostgreSQL first, then a {"match_id": {"$in": [...]}} stage here.
    return [
        {
            "player_id": scorer["_id"],
            "player_name": scorer["player_name"],
            "goals": scorer["goals"],
        }
        for scorer in top_scorers
    ]

"""MongoDB client and the `match_events` collection."""

from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import MONGO_URL

client = AsyncIOMotorClient(MONGO_URL)
mongo_db = client["football"]
events = mongo_db["match_events"]


async def ensure_indexes() -> None:
    """Create the indexes the event queries rely on (no-op if they exist)."""
    await events.create_index([("match_id", 1), ("minute", 1)])
    await events.create_index("type")

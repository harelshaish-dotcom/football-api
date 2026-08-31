import os
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")

client = AsyncIOMotorClient(MONGO_URL)
mongo_db = client["football"]
events = mongo_db["match_events"]


async def ensure_indexes():
    await events.create_index([("match_id", 1), ("minute", 1)])
    await events.create_index("type")
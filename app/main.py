"""FastAPI application entry point: `uvicorn app.main:app --reload`."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.cache import redis_client
from app.core.events import start_producer, stop_producer  # noqa: F401  (used once Kafka is re-enabled below)
from app.db.mongo import ensure_indexes
from app.routes import auth, leagues, matches, players, stats, teams, users

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Prepare MongoDB indexes and check Redis on startup."""
    await ensure_indexes()
    try:
        await redis_client.ping()
        logger.info("Redis connected")
    except Exception as e:
        logger.warning("Redis unreachable: %s", e)

    # await start_producer()

    yield

    # await stop_producer()


app = FastAPI(title="Football API", version="0.2.0", lifespan=lifespan)

app.include_router(stats.router)
app.include_router(teams.router)
app.include_router(users.router)
app.include_router(players.router)
app.include_router(leagues.router)
app.include_router(matches.router)
app.include_router(auth.router)

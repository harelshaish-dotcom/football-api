"""FastAPI application entry point: `uvicorn app.main:app --reload`."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

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

    await start_producer()

    yield

    await stop_producer()


app = FastAPI(title="Football API", version="0.2.0", lifespan=lifespan)


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """Safety net: turn a database constraint violation into a clear 4xx instead of a 500.

    Routes validate references and uniqueness themselves; this only catches what
    slips through (e.g. an explicit null for a required column, or a race).
    """
    orig = exc.orig
    pgcode = getattr(orig, "pgcode", None)
    diag = getattr(orig, "diag", None)
    column = getattr(diag, "column_name", None)
    detail_text = getattr(diag, "message_detail", "") or ""

    if pgcode == "23502":  # not_null_violation
        status_code, detail = 422, f"'{column or 'a required field'}' cannot be null"
    elif pgcode == "23503" and "still referenced" in detail_text:  # FK, on delete
        status_code, detail = 409, "Cannot delete: other records still reference this one"
    elif pgcode == "23503":  # FK, on insert/update
        status_code, detail = 422, "A referenced record does not exist"
    elif pgcode == "23505":  # unique_violation
        status_code, detail = 409, "A record with this value already exists"
    else:
        status_code, detail = 409, "The request conflicts with existing data"

    logger.warning("IntegrityError on %s %s: %s", request.method, request.url.path, orig)
    return JSONResponse(status_code=status_code, content={"detail": detail})


app.include_router(stats.router)
app.include_router(teams.router)
app.include_router(users.router)
app.include_router(players.router)
app.include_router(leagues.router)
app.include_router(matches.router)
app.include_router(auth.router)

"""Redis helpers: response caching, login rate limiting, JWT blocklist, live leaderboard.

Every helper swallows Redis errors and returns a safe fallback, so the API keeps
working (uncached) when Redis is down.
"""

import json
import logging
from typing import Any

import redis.asyncio as redis

from app.core.config import REDIS_URL
from app.db.mongo import events

logger = logging.getLogger(__name__)

redis_client = redis.from_url(REDIS_URL, decode_responses=True)


# --- Response cache ---------------------------------------------------------


async def get_cached(key: str) -> Any | None:
    """Return the cached JSON value for `key`, or None on a miss or error."""
    try:
        value = await redis_client.get(key)
        if value:
            return json.loads(value)
        return None
    except Exception as e:
        logger.warning("Cache get error: %s", e)
        return None


async def set_cached(key: str, value: Any, ttl: int = 300) -> bool:
    """Store `value` as JSON under `key` for `ttl` seconds."""
    try:
        await redis_client.setex(key, ttl, json.dumps(value, default=str))
        return True
    except Exception as e:
        logger.warning("Cache set error: %s", e)
        return False


async def delete_cached(key: str) -> bool:
    """Remove `key` from the cache."""
    try:
        await redis_client.delete(key)
        return True
    except Exception as e:
        logger.warning("Cache delete error: %s", e)
        return False


# --- Rate limiting ----------------------------------------------------------


async def check_rate_limit(
    key: str, max_attempts: int = 5, window_seconds: int = 60
) -> tuple[bool, int]:
    """Count one attempt for `key`.

    Returns (is_allowed, remaining_attempts). Fails open if Redis is unavailable.
    """
    try:
        # One MULTI/EXEC transaction: create the key with its expiry if it doesn't
        # exist yet (NX), then count the attempt. The key can never exist without
        # a TTL, so a crash can't leave an IP locked out forever.
        async with redis_client.pipeline(transaction=True) as pipe:
            pipe.set(key, 0, ex=window_seconds, nx=True)
            pipe.incr(key)
            _, current = await pipe.execute()

        remaining = max(0, max_attempts - current)
        is_allowed = current <= max_attempts
        return is_allowed, remaining
    except Exception as e:
        logger.warning("Rate limit check error: %s", e)
        return True, max_attempts  # Allow on error


async def get_rate_limit_ttl(key: str) -> int:
    """Seconds until the rate-limit window for `key` resets."""
    try:
        ttl = await redis_client.ttl(key)
        return max(0, ttl)
    except Exception as e:
        logger.warning("Rate limit TTL error: %s", e)
        return 0


# --- JWT blocklist (logout) -------------------------------------------------


async def add_to_blocklist(jti: str, ttl: int) -> bool:
    """Block the token with ID `jti` for `ttl` seconds (its remaining lifetime)."""
    try:
        key = f"blocklist:jti:{jti}"
        await redis_client.setex(key, ttl, "1")
        return True
    except Exception as e:
        logger.warning("Blocklist add error: %s", e)
        return False


async def is_token_blocked(jti: str) -> bool:
    """True if the token with ID `jti` has been logged out."""
    try:
        key = f"blocklist:jti:{jti}"
        exists = await redis_client.exists(key)
        return exists == 1
    except Exception as e:
        logger.warning("Blocklist check error: %s", e)
        return False


# --- Live leaderboard -------------------------------------------------------


async def rebuild_leaderboard(season: int = 1) -> bool:
    """Recompute the leaderboard from the goal events in MongoDB (the source of truth).

    The new board is built under a temporary key and swapped in with RENAME, so
    readers never see a half-built board. Returns False if Mongo or Redis failed.
    """
    key = f"leaderboard:season:{season}"
    tmp_key = f"{key}:rebuild"
    try:
        pipeline = [
            {"$match": {"type": "goal", "player.id": {"$ne": None}}},
            {"$group": {"_id": "$player.id", "goals": {"$sum": 1}}},
        ]
        rows = await events.aggregate(pipeline).to_list(length=None)
        scores = {f"player:{r['_id']}": r["goals"] for r in rows}

        async with redis_client.pipeline(transaction=True) as pipe:
            if scores:
                pipe.delete(tmp_key)
                pipe.zadd(tmp_key, scores)
                pipe.rename(tmp_key, key)
            else:
                pipe.delete(key)
            await pipe.execute()
        return True
    except Exception as e:
        logger.warning("Leaderboard rebuild error: %s", e)
        return False


async def get_top_scorers(limit: int = 10, season: int = 1) -> list[dict]:
    """Get top N scorers from leaderboard using ZREVRANGE"""
    try:
        key = f"leaderboard:season:{season}"
        # ZREVRANGE returns [(member, score), ...] with WITHSCORES
        results = await redis_client.zrevrange(key, 0, limit - 1, withscores=True)

        scorers = []
        for member, score in results:
            # member is "player:{player_id}"
            player_id = int(member.split(":")[1])
            scorers.append({"player_id": player_id, "goals": int(score), "rank": len(scorers) + 1})
        return scorers
    except Exception as e:
        logger.warning("Get top scorers error: %s", e)
        return []

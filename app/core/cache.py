"""Redis helpers: response caching, login rate limiting, JWT blocklist, live leaderboard.

Every helper swallows Redis errors and returns a safe fallback, so the API keeps
working (uncached) when Redis is down.
"""

import json
import logging
from typing import Any

import redis.asyncio as redis

from app.core.config import REDIS_URL

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
        current = await redis_client.incr(key)
        if current == 1:
            # First attempt in this window, set expiry
            await redis_client.expire(key, window_seconds)

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


async def update_leaderboard(player_id: int, season: int = 1) -> int:
    """Increment player's goal count in leaderboard sorted set. Returns new score."""
    try:
        key = f"leaderboard:season:{season}"
        new_score = await redis_client.zincrby(key, 1, f"player:{player_id}")
        return int(float(new_score))
    except Exception as e:
        logger.warning("Leaderboard update error: %s", e)
        return 0


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

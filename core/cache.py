import redis.asyncio as redis
import json
import asyncio

r = redis.from_url("redis://localhost:6379", decode_responses=True)


async def get_cached(key: str):
    """Get value from cache"""
    try:
        value = await r.get(key)
        if value:
            return json.loads(value)
        return None
    except Exception as e:
        print(f"Cache get error: {e}")
        return None


async def set_cached(key: str, value, ttl: int = 300):
    """Set value in cache with TTL (in seconds)"""
    try:
        await r.setex(key, ttl, json.dumps(value, default=str))
        return True
    except Exception as e:
        print(f"Cache set error: {e}")
        return False


async def delete_cached(key: str):
    """Delete value from cache"""
    try:
        await r.delete(key)
        return True
    except Exception as e:
        print(f"Cache delete error: {e}")
        return False


async def invalidate_pattern(pattern: str):
    """Delete all keys matching a pattern"""
    try:
        cursor = 0
        count = 0
        while True:
            cursor, keys = await r.scan(cursor, match=pattern, count=100)
            if keys:
                await r.delete(*keys)
                count += len(keys)
            if cursor == 0:
                break
        return count
    except Exception as e:
        print(f"Cache invalidate pattern error: {e}")
        return 0


async def check_rate_limit(key: str, max_attempts: int = 5, window_seconds: int = 60) -> tuple[bool, int]:
    """
    Check if rate limit is exceeded.
    Returns: (is_allowed, remaining_attempts)
    """
    try:
        current = await r.incr(key)
        if current == 1:
            # First attempt in this window, set expiry
            await r.expire(key, window_seconds)
        
        remaining = max(0, max_attempts - current)
        is_allowed = current <= max_attempts
        return is_allowed, remaining
    except Exception as e:
        print(f"Rate limit check error: {e}")
        return True, max_attempts  # Allow on error


async def get_rate_limit_ttl(key: str) -> int:
    """Get remaining TTL for rate limit key in seconds"""
    try:
        ttl = await r.ttl(key)
        return max(0, ttl)
    except Exception as e:
        print(f"Rate limit TTL error: {e}")
        return 0


async def add_to_blocklist(jti: str, ttl: int) -> bool:
    """Add JWT to blocklist with TTL"""
    try:
        key = f"blocklist:jti:{jti}"
        await r.setex(key, ttl, "1")
        return True
    except Exception as e:
        print(f"Blocklist add error: {e}")
        return False


async def is_token_blocked(jti: str) -> bool:
    """Check if JWT is in blocklist"""
    try:
        key = f"blocklist:jti:{jti}"
        exists = await r.exists(key)
        return exists == 1
    except Exception as e:
        print(f"Blocklist check error: {e}")
        return False


async def update_leaderboard(player_id: int, season: int = 1) -> int:
    """Increment player's goal count in leaderboard sorted set. Returns new score."""
    try:
        key = f"leaderboard:season:{season}"
        new_score = await r.zincrby(key, 1, f"player:{player_id}")
        return int(float(new_score))
    except Exception as e:
        print(f"Leaderboard update error: {e}")
        return 0


async def get_top_scorers(limit: int = 10, season: int = 1) -> list[dict]:
    """Get top N scorers from leaderboard using ZREVRANGE"""
    try:
        key = f"leaderboard:season:{season}"
        # ZREVRANGE returns [(member, score), ...] with WITHSCORES
        results = await r.zrevrange(key, 0, limit - 1, withscores=True)
        
        scorers = []
        for member, score in results:
            # member is "player:{player_id}"
            player_id = int(member.split(":")[1])
            scorers.append({
                "player_id": player_id,
                "goals": int(score),
                "rank": len(scorers) + 1
            })
        return scorers
    except Exception as e:
        print(f"Get top scorers error: {e}")
        return []
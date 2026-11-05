"""FastAPI dependencies: authentication, Redis access and rate limiting."""

from collections.abc import Awaitable, Callable

import redis.asyncio as redis
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.cache import check_rate_limit, get_rate_limit_ttl, is_token_blocked, redis_client
from app.core.security import decode_token
from app.db.postgres import get_db
from app.models.user import User

oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/token")


def get_redis() -> redis.Redis:
    """The shared Redis client (one connection pool for the whole app).

    Injecting it with Depends(get_redis) instead of importing it lets tests swap
    it out with app.dependency_overrides.
    """
    return redis_client


async def get_current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    """Resolve the bearer token to an active user, or raise 401."""
    creds_error = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if payload is None:
        raise creds_error

    # Check if token is in blocklist (logged out)
    jti = payload.get("jti")
    if jti and await is_token_blocked(jti):
        raise creds_error

    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise creds_error
    return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    """Like get_current_user, but also require admin rights (403 otherwise)."""
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return user


# --- Rate limiting ----------------------------------------------------------

READ_LIMIT = 60  # GET requests per caller per minute
WRITE_LIMIT = 20  # POST/PATCH/PUT/DELETE requests per caller per minute
WINDOW_SECONDS = 60


def _caller_identity(request: Request) -> str:
    """`user:{id}` for a request with a valid Bearer token, otherwise `ip:{address}`.

    Never raises: a missing, malformed or expired token just falls back to the IP.
    (Only the signature is checked here, not the blocklist, to keep this cheap.)
    """
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        payload = decode_token(auth.removeprefix("Bearer ").strip())
        if payload and payload.get("sub"):
            return f"user:{payload['sub']}"
    return f"ip:{request.client.host if request.client else 'unknown'}"


RateLimitDependency = Callable[[Request, redis.Redis], Awaitable[None]]


def rate_limit(max_requests: int, window_seconds: int, scope: str) -> RateLimitDependency:
    """Build a dependency allowing `max_requests` per caller per `window_seconds`.

    Key: rate:{scope}:user:{id} or rate:{scope}:ip:{ip}. Over the limit -> 429 with
    Retry-After. Fails open (request allowed) if Redis is unavailable.

        @router.get("/x", dependencies=[Depends(rate_limit(10, 60, "x"))])
    """

    async def dependency(request: Request, r: redis.Redis = Depends(get_redis)) -> None:
        key = f"rate:{scope}:{_caller_identity(request)}"
        is_allowed, _ = await check_rate_limit(
            key, max_attempts=max_requests, window_seconds=window_seconds, client=r
        )
        if not is_allowed:
            retry_after = await get_rate_limit_ttl(key, client=r)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later.",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency


_read_limit = rate_limit(READ_LIMIT, WINDOW_SECONDS, "read")
_write_limit = rate_limit(WRITE_LIMIT, WINDOW_SECONDS, "write")


async def api_rate_limit(request: Request, r: redis.Redis = Depends(get_redis)) -> None:
    """General API limit, attached to whole routers: reads and writes have separate budgets."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        await _read_limit(request, r)
    else:
        await _write_limit(request, r)

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.controllers import auth as auth_ctl
from app.core.cache import add_to_blocklist, check_rate_limit, get_rate_limit_ttl
from app.core.deps import api_rate_limit
from app.core.responses import errors
from app.core.security import create_access_token, decode_token
from app.db.postgres import get_db
from app.schemas.user import UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(api_rate_limit)],
    responses=errors((409, "A user with that email already exists"), 429),
)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    """Create a new (non-admin) user account."""
    email = str(payload.email).lower()
    if auth_ctl.get_by_email(db, email):
        raise HTTPException(status_code=409, detail="A user with that email already exists")
    return auth_ctl.create_user(db, payload)


async def _enforce_login_rate_limit(request: Request) -> None:
    """429 after 5 login attempts per minute from the same IP.

    Shared by /login and /token so both count against one budget.
    """
    client_ip = request.client.host if request.client else "unknown"
    rate_limit_key = f"login_attempts:{client_ip}"

    is_allowed, _ = await check_rate_limit(rate_limit_key, max_attempts=5, window_seconds=60)
    if not is_allowed:
        retry_after = await get_rate_limit_ttl(rate_limit_key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )


@router.post(
    "/login",
    responses=errors(
        (401, "Invalid email or password"),
        (429, "Too many login attempts (5 per minute per IP); see Retry-After"),
    ),
)
async def login(payload: UserCreate, request: Request, db: Session = Depends(get_db)):
    """Log in with a JSON body. Limited to 5 attempts per minute per IP."""
    await _enforce_login_rate_limit(request)

    email = str(payload.email).lower()
    user = auth_ctl.authenticate(db, email, payload.password)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {
        "access_token": create_access_token(user.id, user.is_admin),
        "token_type": "bearer",
    }


@router.post(
    "/token",
    responses=errors(
        (401, "Invalid email or password"),
        (429, "Too many login attempts (5 per minute per IP, shared with /login)"),
    ),
)
async def login_form(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Log in with a form (used by the Authorize button in /docs). Same rate limit as /login."""
    await _enforce_login_rate_limit(request)

    user = auth_ctl.authenticate(db, form.username.lower(), form.password)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"access_token": create_access_token(user.id, user.is_admin), "token_type": "bearer"}


@router.post(
    "/logout",
    dependencies=[Depends(api_rate_limit)],
    responses=errors(
        (400, "Token has no jti/exp claims"),
        (401, "Missing or invalid token"),
        429,
        (503, "Redis unavailable, the token could not be blocked"),
    ),
)
async def logout(request: Request):
    """Log out by adding the current token to the Redis blocklist."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid token"
        )

    token = auth_header.split(" ")[1]
    payload = decode_token(token)

    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    jti = payload.get("jti")
    exp = payload.get("exp")

    if not jti or not exp:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token claims")

    # Block the token only for the rest of its lifetime (exp is a Unix timestamp)
    now = datetime.now(UTC).timestamp()
    ttl = int(exp - now)

    # Don't claim success if the token wasn't actually blocked.
    if ttl > 0 and not await add_to_blocklist(jti, ttl):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Logout is temporarily unavailable, please try again",
        )

    return {"detail": "Successfully logged out"}

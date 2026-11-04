import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.controllers import auth as auth_ctl
from app.core.cache import add_to_blocklist, check_rate_limit, get_rate_limit_ttl
from app.core.security import create_access_token, decode_token
from app.db.postgres import get_db
from app.schemas.user import UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    """Create a new (non-admin) user account."""
    email = str(payload.email).lower()
    if auth_ctl.get_by_email(db, email):
        raise HTTPException(status_code=409, detail="A user with that email already exists")
    return auth_ctl.create_user(db, payload)


@router.post("/login")
def login(payload: UserCreate, db: Session = Depends(get_db), request: Request = None):
    """Log in with a JSON body. Limited to 5 attempts per minute per IP."""
    # Get client IP for rate limiting
    client_ip = request.client.host if request and request.client else "unknown"
    rate_limit_key = f"login_attempts:{client_ip}"

    # Check rate limit: 5 attempts per 60 seconds
    is_allowed, remaining = asyncio.run(
        check_rate_limit(rate_limit_key, max_attempts=5, window_seconds=60)
    )

    if not is_allowed:
        retry_after = asyncio.run(get_rate_limit_ttl(rate_limit_key))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )

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


@router.post("/token")
def login_form(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Log in with a form (used by the Authorize button in /docs)."""
    user = auth_ctl.authenticate(db, form.username.lower(), form.password)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"access_token": create_access_token(user.id, user.is_admin), "token_type": "bearer"}


@router.post("/logout")
def logout(request: Request):
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

    if ttl > 0:
        asyncio.run(add_to_blocklist(jti, ttl))

    return {"detail": "Successfully logged out"}

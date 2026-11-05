"""FastAPI dependencies for authenticated routes."""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.cache import is_token_blocked
from app.core.security import decode_token
from app.db.postgres import get_db
from app.models.user import User

oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/token")


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

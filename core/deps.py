from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from database.connection import get_db
from core.security import decode_token
from models.user import User
from core.cache import is_token_blocked
import asyncio

oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(token: str = Depends(oauth2),
                     db: Session = Depends(get_db)) -> User:
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
    if jti:
        is_blocked = asyncio.run(is_token_blocked(jti))
        if is_blocked:
            raise creds_error
    
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise creds_error
    return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            detail="Admin privileges required")
    return user
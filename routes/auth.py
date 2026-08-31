from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from controllers import auth as auth_ctl
from core.security import create_access_token, decode_token, ACCESS_TOKEN_MINUTES
from database.postgres import get_db
from schemas.user import UserCreate, UserOut
from core.cache import check_rate_limit, get_rate_limit_ttl, add_to_blocklist
from core.deps import get_current_user
import asyncio
from datetime import datetime, timezone

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    email = str(payload.email).lower()
    if auth_ctl.get_by_email(db, email):
        raise HTTPException(status_code=409, detail="A user with that email already exists")
    return auth_ctl.create_user(db, payload)


@router.post("/login")
def login(payload: UserCreate, db: Session = Depends(get_db), request: Request = None):
    # Get client IP for rate limiting
    client_ip = request.client.host if request and request.client else "unknown"
    rate_limit_key = f"login_attempts:{client_ip}"
    
    # Check rate limit: 5 attempts per 60 seconds
    is_allowed, remaining = asyncio.run(check_rate_limit(rate_limit_key, max_attempts=5, window_seconds=60))
    
    if not is_allowed:
        # Rate limit exceeded
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


@router.post("/logout")
def logout(request: Request):
    """Logout by adding JWT to blocklist"""
    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Missing or invalid token"
        )
    
    token = auth_header.split(" ")[1]
    payload = decode_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid token"
        )
    
    jti = payload.get("jti")
    exp = payload.get("exp")
    
    if not jti or not exp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Invalid token claims"
        )
    
    # Calculate remaining TTL (exp is already a Unix timestamp from jwt.encode)
    now = datetime.now(timezone.utc).timestamp()
    ttl = int(exp - now)
    
    if ttl > 0:
        # Add to blocklist
        asyncio.run(add_to_blocklist(jti, ttl))
    
    return {"detail": "Successfully logged out"}
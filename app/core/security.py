"""Password hashing and JWT access tokens."""

import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt

from app.core.config import SECRET_KEY as _SECRET_KEY

if _SECRET_KEY is None:
    raise RuntimeError("SECRET_KEY is not set (add it to .env)")  # crash loudly if unset

SECRET_KEY: str = _SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = 30


def hash_password(plain: str) -> str:
    """Hash a plain-text password with bcrypt."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Check a plain-text password against a bcrypt hash."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: int, is_admin: bool) -> str:
    """Create a signed JWT for `user_id` that expires after ACCESS_TOKEN_MINUTES."""
    now = datetime.now(UTC)
    exp = now + timedelta(minutes=ACCESS_TOKEN_MINUTES)
    claims = {
        "sub": str(user_id),
        "admin": is_admin,
        "jti": str(uuid.uuid4()),  # JWT ID for logout blocklist
        "iat": now,
        "exp": exp,
    }
    return jwt.encode(claims, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    """Return the token's claims, or None if it is invalid or expired."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None

from datetime import datetime, timedelta, timezone
import bcrypt
from jose import jwt, JWTError
import os
import uuid


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())

SECRET_KEY = os.environ["SECRET_KEY"]      # crash loudly if unset
ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = 30


def create_access_token(user_id: int, is_admin: bool) -> str:
    now = datetime.now(timezone.utc)
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
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None

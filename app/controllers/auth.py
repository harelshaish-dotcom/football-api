"""Database operations for user accounts."""

from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserCreate


def get_by_email(db: Session, email: str) -> User | None:
    """Find a user by exact (already lower-cased) email."""
    return db.query(User).filter(User.email == email).first()


def create_user(db: Session, payload: UserCreate) -> User:
    """Create a user with a hashed password. Emails are stored lower-case."""
    user = User(
        email=str(payload.email).lower(),
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    """Return the user if the email/password pair is valid, else None."""
    user = get_by_email(db, email.lower())
    if user is None or not verify_password(password, user.hashed_password):
        return None
    return user

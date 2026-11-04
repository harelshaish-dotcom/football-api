"""PostgreSQL engine, session factory and the declarative Base for all models."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True, echo=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Iterator[Session]:
    """FastAPI dependency: yield a session and always close it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

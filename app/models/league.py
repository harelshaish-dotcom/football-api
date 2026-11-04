from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from app.db.postgres import Base


class League(Base):
    """A football league (e.g. Premier League) containing many teams."""

    __tablename__ = "leagues"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    country = Column(String(50), nullable=False, index=True)
    date_founded = Column(DateTime, nullable=False, index=True)

    teams = relationship("Team", back_populates="league")

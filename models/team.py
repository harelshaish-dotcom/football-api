from sqlalchemy import Column, Integer, String, DateTime, func
from database.connection import Base


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(60), nullable=False, unique=True, index=True)
    league_id = Column(Integer, nullable=False, index=True)
    founded = Column(Integer, nullable=True)
    stadium = Column(String(120), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
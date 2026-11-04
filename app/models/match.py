from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.postgres import Base


class Match(Base):
    """A fixture between two teams. Its events live in MongoDB (`match_events`)."""

    __tablename__ = "matches"

    id = Column(Integer, primary_key=True)
    home_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    away_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    home_score = Column(Integer, default=0)
    away_score = Column(Integer, default=0)
    matchday = Column(Integer, nullable=False)
    status = Column(String(20), default="scheduled")  # scheduled, live, finished
    kickoff_time = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="home_matches")
    away_team = relationship("Team", foreign_keys=[away_team_id], back_populates="away_matches")

from sqlalchemy import Column, Integer, String, DateTime, func, ForeignKey
from database.connection import Base
import datetime
from sqlalchemy.orm import relationship
from models.user import follows
home_matches = relationship("Match", foreign_keys="Match.home_team_id", back_populates="home_team")
away_matches = relationship("Match", foreign_keys="Match.away_team_id", back_populates="away_team")

from models import Base

class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True)
    name = Column(String(60), unique=True, nullable=False, index=True)
    country = Column(String(50), nullable=False, index=True)
    stadium = Column(String(120), nullable=False)
    followers = relationship(
    "User",
    secondary=follows,
    back_populates="followed_teams")
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False, index=True)
    date_founded = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    league = relationship("League", back_populates="teams")
    players = relationship("Player", back_populates="team")
    home_matches = relationship("Match", foreign_keys="Match.home_team_id", back_populates="home_team")
    away_matches = relationship("Match", foreign_keys="Match.away_team_id", back_populates="away_team")
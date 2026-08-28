from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, func
from database.connection import Base
from sqlalchemy.orm import relationship


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    age = Column(Integer, nullable=False, index=True)
    position = Column(String(50), nullable=False, index=True)
    shirt_number = Column(Integer, nullable=False, index=True)
    height = Column(Integer, nullable=False, index=True)
    country = Column(String(50), nullable=False, index=True)
    value = Column(Integer, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)

    team = relationship("Team", back_populates="players")
from sqlalchemy import Column, Integer, String, DateTime
from database.connection import Base
from sqlalchemy.orm import relationship


class League(Base):
    __tablename__ = "leagues"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    country = Column(String(50), nullable=False, index=True)
    date_founded = Column(DateTime, nullable=False, index=True)

    teams = relationship("Team", back_populates="league")
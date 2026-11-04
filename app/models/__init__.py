"""SQLAlchemy models. Importing this package registers every table on Base.metadata."""

from app.db.postgres import Base
from app.models.enums import POSITIONS
from app.models.league import League
from app.models.match import Match
from app.models.player import Player
from app.models.team import Team
from app.models.user import User, follows

__all__ = ["POSITIONS", "Base", "League", "Match", "Player", "Team", "User", "follows"]

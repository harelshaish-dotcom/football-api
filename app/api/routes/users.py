from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.postgres import get_db
from app.models import Match, User
from app.schemas.user import UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me/feed")
def get_user_feed(db: Session = Depends(get_db)):
    """Upcoming matches of the teams the user follows."""
    user_id = 1  # TODO: get from auth

    matches = (
        db.query(Match)
        .join(Match.home_team)
        .join(User.followed_teams)
        .filter(User.id == user_id)
        .filter(Match.status == "scheduled")
        .order_by(Match.kickoff_time)
        .all()
    )

    return {"matches": matches}


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    """The logged-in user's profile."""
    return current_user

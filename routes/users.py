from fastapi import APIRouter, Depends
from core.deps import get_current_user
from schemas.user import UserOut
from sqlalchemy.orm import Session
from database.connection import get_db
from models import Match, User

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me/feed")
def get_user_feed(db: Session = Depends(get_db)):
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
    return current_user
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from controllers import auth as auth_ctl
from core.security import create_access_token
from database.postgres import get_db
from schemas.user import UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    email = str(payload.email).lower()
    if auth_ctl.get_by_email(db, email):
        raise HTTPException(status_code=409, detail="A user with that email already exists")
    return auth_ctl.create_user(db, payload)


@router.post("/login")
def login(payload: UserCreate, db: Session = Depends(get_db)):
    email = str(payload.email).lower()
    user = auth_ctl.authenticate(db, email, payload.password)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {
        "access_token": create_access_token(user.id, user.is_admin),
        "token_type": "bearer",
    }
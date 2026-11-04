from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """Body of POST /auth/register and POST /auth/login."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    """A user as returned by the API (never includes the password hash)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    is_admin: bool
    is_active: bool
    created_at: datetime

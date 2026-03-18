"""Auth API: /api/auth/me, /api/auth/login"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import get_current_user, require_approved
from src.database import get_db
from src.db_models import User

router = APIRouter()


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    is_approved: bool
    is_admin: bool


def _to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_approved=user.is_approved,
        is_admin=user.is_admin,
    )


@router.post("/login", response_model=UserResponse)
async def login(user: User = Depends(get_current_user)):
    """Called after the client obtains an Azure AD token.
    Registers the user in the DB (if new) and returns their profile.
    Does NOT require approval – used to check approval status.
    """
    return _to_response(user)


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    """Return current user profile (no approval required)."""
    return _to_response(user)

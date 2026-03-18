"""Admin API: /api/admin/users — user approval & role management (admin only)."""
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.auth import require_admin
from src.database import get_db
from src.db_models import User

router = APIRouter()


class UserSummary(BaseModel):
    id: str
    email: str
    display_name: str
    is_approved: bool
    is_admin: bool
    created_at: str
    last_login_at: str | None


class UserActionResponse(BaseModel):
    status: Literal["ok"]
    user: UserSummary


def _to_summary(u: User) -> UserSummary:
    return UserSummary(
        id=u.id,
        email=u.email,
        display_name=u.display_name,
        is_approved=u.is_approved,
        is_admin=u.is_admin,
        created_at=u.created_at.isoformat(),
        last_login_at=u.last_login_at.isoformat() if u.last_login_at else None,
    )


@router.get("/users", response_model=list[UserSummary])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(User).order_by(User.created_at))
    users = result.scalars().all()
    return [_to_summary(u) for u in users]


@router.post("/users/{user_id}/approve", response_model=UserActionResponse)
async def approve_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_approved = True
    await db.commit()
    await db.refresh(user)
    return UserActionResponse(status="ok", user=_to_summary(user))


@router.post("/users/{user_id}/reject", response_model=UserActionResponse)
async def reject_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_approved = False
    await db.commit()
    await db.refresh(user)
    return UserActionResponse(status="ok", user=_to_summary(user))


@router.post("/users/{user_id}/toggle-admin", response_model=UserActionResponse)
async def toggle_admin(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot change your own admin status")
    user.is_admin = not user.is_admin
    await db.commit()
    await db.refresh(user)
    return UserActionResponse(status="ok", user=_to_summary(user))

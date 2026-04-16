"""Authentication: Windows username based (DEV_AUTH_BYPASS only).

Environment variables:
  DEV_AUTH_BYPASS      - Must be "true". Azure AD is not supported.
"""
import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from src.database import get_db
from src.db_models import User

logger = logging.getLogger("bsapp.auth")

DEV_AUTH_BYPASS = os.environ.get("DEV_AUTH_BYPASS", "false").lower() == "true"
DEV_USER_RETENTION_DAYS = int(os.environ.get("DEV_USER_RETENTION_DAYS", "30"))

security = HTTPBearer(auto_error=False)


async def _get_or_create_windows_user(
    db: AsyncSession,
    windows_username: str,
) -> User:
    """Windowsユーザー名を唯一の識別子としてユーザーを取得または作成する。

    メールアドレスは {windows_username}@dev.local で固定。
    """
    email = f"{windows_username}@dev.local"
    now = datetime.now(timezone.utc)

    # windows_username で検索（既存ユーザー）
    result = await db.execute(
        select(User).where(User.windows_username == windows_username)
    )
    user = result.scalar_one_or_none()

    if user is not None:
        user.last_login_at = now
        # emailが古いフォーマット (dev_uuid@dev.local) のまま残っている場合は更新
        if user.email != email:
            old_email = user.email
            user.email = email
            logger.info(
                f"User email updated for windows_username={windows_username}: "
                f"{old_email} → {email}"
            )
        await db.commit()
        await db.refresh(user)
        return user

    # emailで検索（windows_usernameカラムが未設定の古いレコードへの対応）
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is not None:
        user.windows_username = windows_username
        user.last_login_at = now
        await db.commit()
        await db.refresh(user)
        logger.info(f"windows_username set for existing user: {email}")
        return user

    # 新規作成
    count_result = await db.execute(select(func.count()).select_from(User))
    total_users = count_result.scalar_one()
    is_first = total_users == 0

    user = User(
        id=str(uuid.uuid4()),
        email=email,
        display_name=windows_username,
        azure_oid=None,
        is_approved=True,
        is_admin=is_first,
        created_at=now,
        last_login_at=now,
        windows_username=windows_username,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    logger.info(
        f"New user created: windows_username={windows_username} "
        f"(is_admin={is_first})"
    )
    return user


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency: Windowsユーザー名でユーザーを返す。

    X-Windows-Username ヘッダが必須。DEV_AUTH_BYPASS=true が前提。
    """
    if not DEV_AUTH_BYPASS:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DEV_AUTH_BYPASS=true が必要です。Azure AD 認証は無効化されています。",
        )

    windows_username = request.headers.get("x-windows-username", "").strip()
    if not windows_username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Windows-Username ヘッダが必要です。",
        )

    return await _get_or_create_windows_user(db, windows_username)


async def require_approved(user: User = Depends(get_current_user)) -> User:
    """Dependency that additionally requires the user to be approved."""
    if not user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is pending admin approval",
        )
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Dependency that requires admin rights."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


async def cleanup_stale_dev_users(db: AsyncSession) -> int:
    """DEV_USER_RETENTION_DAYS 日以上アクセスのない @dev.local ユーザーを削除する。"""
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=DEV_USER_RETENTION_DAYS)
    result = await db.execute(
        select(User).where(
            User.email.like("%@dev.local"),
            User.last_login_at < cutoff,
        )
    )
    stale_users = result.scalars().all()
    for user in stale_users:
        await db.delete(user)
    await db.commit()
    if stale_users:
        logger.info(
            f"Cleaned up {len(stale_users)} stale dev user(s) "
            f"(no access for {DEV_USER_RETENTION_DAYS}+ days)"
        )
    return len(stale_users)

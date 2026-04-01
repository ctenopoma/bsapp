"""Authentication: Azure AD JWT validation with optional dev-mode bypass.

Environment variables:
  AZURE_TENANT_ID      - Azure AD tenant ID (required unless DEV_AUTH_BYPASS=true)
  AZURE_CLIENT_ID      - App registration client ID
  DEV_AUTH_BYPASS      - Set to "true" to skip JWT validation (dev only)
  DEV_USER_EMAIL       - Email used in dev bypass mode (default: dev@example.com)
  DEV_USER_NAME        - Display name in dev bypass mode (default: Dev User)
"""
import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from src.database import get_db
from src.db_models import User

logger = logging.getLogger("bsapp.auth")

AZURE_TENANT_ID = os.environ.get("AZURE_TENANT_ID", "")
AZURE_CLIENT_ID = os.environ.get("AZURE_CLIENT_ID", "")
DEV_AUTH_BYPASS = os.environ.get("DEV_AUTH_BYPASS", "false").lower() == "true"
DEV_USER_EMAIL = os.environ.get("DEV_USER_EMAIL", "dev@example.com")
DEV_USER_NAME = os.environ.get("DEV_USER_NAME", "Dev User")
DEV_USER_RETENTION_DAYS = int(os.environ.get("DEV_USER_RETENTION_DAYS", "30"))

_jwks_cache: dict | None = None

security = HTTPBearer(auto_error=False)


async def _get_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache
    url = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}/discovery/v2.0/keys"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=10)
        resp.raise_for_status()
    _jwks_cache = resp.json()
    return _jwks_cache


def _decode_token(token: str) -> dict:
    """Validate and decode a Microsoft JWT.  Returns claims dict."""
    if not AZURE_TENANT_ID or not AZURE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AZURE_TENANT_ID / AZURE_CLIENT_ID not configured on server",
        )
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        jwks = loop.run_until_complete(_get_jwks())
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Failed to fetch JWKS: {e}")

    try:
        claims = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=AZURE_CLIENT_ID,
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        )
    return claims


async def _get_or_create_user(
    db: AsyncSession,
    email: str,
    display_name: str,
    azure_oid: Optional[str],
    force_approved: bool = False,
    client_ip: Optional[str] = None,
) -> User:
    """Find existing user by email or OID, or create a new pending user.
    The very first user ever gets auto-approved + admin rights.
    If force_approved=True, the user is always approved + admin (used in DEV_AUTH_BYPASS).
    """
    # Try to find by azure_oid first, then by email
    user: User | None = None
    if azure_oid:
        result = await db.execute(select(User).where(User.azure_oid == azure_oid))
        user = result.scalar_one_or_none()
    if user is None:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if user is None:
        # Check if this is the very first user
        count_result = await db.execute(select(func.count()).select_from(User))
        total_users = count_result.scalar_one()
        is_first = total_users == 0

        approved = force_approved or is_first
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            display_name=display_name,
            azure_oid=azure_oid,
            is_approved=approved,
            is_admin=approved,
            created_at=now,
            last_login_at=now,
            last_known_ip=client_ip,
        )
        db.add(user)
        if force_approved:
            logger.info(f"Dev user {email} created with admin + auto-approved")
        elif is_first:
            logger.info(f"First user {email} created with admin + auto-approved")
        else:
            logger.info(f"New user {email} created (pending approval)")
    else:
        # Update fields if changed
        user.display_name = display_name
        if azure_oid:
            user.azure_oid = azure_oid
        user.last_login_at = now
        if client_ip:
            user.last_known_ip = client_ip
        if force_approved and (not user.is_approved or not user.is_admin):
            user.is_approved = True
            user.is_admin = True
            logger.info(f"Dev user {email} upgraded to approved + admin")

    await db.commit()
    await db.refresh(user)
    return user


async def _get_or_create_dev_user(
    db: AsyncSession,
    session_id: str,
    client_ip: Optional[str],
) -> User:
    """DEV_AUTH_BYPASS 用: session_id でユーザーを検索し、なければ IP で検索してセッション再紐付けする。
    どちらも見つからない場合は新規作成。
    """
    email = f"dev_{session_id}@dev.local"
    short_id = session_id[:8]
    display_name = f"Dev User ({short_id})"
    now = datetime.now(timezone.utc)

    # 1. セッションIDで検索（通常ルート）
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is not None:
        user.last_login_at = now
        if client_ip:
            user.last_known_ip = client_ip
        await db.commit()
        await db.refresh(user)
        return user

    # 2. セッションID未知 → IPで既存dev.localユーザーを検索（localStorage削除後の復元）
    if client_ip:
        result = await db.execute(
            select(User)
            .where(User.last_known_ip == client_ip)
            .where(User.email.like("%@dev.local"))
            .order_by(User.last_login_at.desc())
            .limit(1)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            old_email = existing.email
            existing.email = email
            existing.display_name = display_name
            existing.last_login_at = now
            existing.last_known_ip = client_ip
            await db.commit()
            await db.refresh(existing)
            logger.info(
                f"Dev user re-associated by IP {client_ip}: {old_email} → {email}"
            )
            return existing

    # 3. 完全新規
    count_result = await db.execute(select(func.count()).select_from(User))
    is_first = count_result.scalar_one() == 0
    user = User(
        id=str(uuid.uuid4()),
        email=email,
        display_name=display_name,
        azure_oid=None,
        is_approved=True,
        is_admin=True,
        created_at=now,
        last_login_at=now,
        last_known_ip=client_ip,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    logger.info(f"Dev user {email} created (IP: {client_ip}, first={is_first})")
    return user


async def cleanup_stale_dev_users(db: AsyncSession) -> int:
    """DEV_USER_RETENTION_DAYS 日以上アクセスのない @dev.local ユーザーを削除する。
    User の cascade 設定により関連データも全て削除される。
    Returns: 削除したユーザー数
    """
    from datetime import timedelta
    from sqlalchemy import delete

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


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency: returns the authenticated User row.

    In DEV_AUTH_BYPASS mode the token is ignored and a per-browser dev user is used.
    The browser sends a persistent session ID via X-Dev-Session-Id header;
    different browsers/machines get different user records.
    Otherwise validates the Azure AD Bearer JWT.
    """
    client_ip: Optional[str] = request.client.host if request.client else None

    if DEV_AUTH_BYPASS:
        session_id = request.headers.get("x-dev-session-id", "default")
        user = await _get_or_create_dev_user(db, session_id=session_id, client_ip=client_ip)
        return user

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    claims = _decode_token(credentials.credentials)
    email: str = claims.get("preferred_username") or claims.get("upn") or claims.get("email", "")
    display_name: str = claims.get("name") or claims.get("given_name", "") or email
    oid: str = claims.get("oid", "")

    if not email:
        raise HTTPException(status_code=401, detail="Token missing email claim")

    user = await _get_or_create_user(
        db, email=email, display_name=display_name, azure_oid=oid, client_ip=client_ip
    )
    return user


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

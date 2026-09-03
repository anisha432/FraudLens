"""FastAPI dependencies for authentication and activity logging."""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_session
from app.db.session import get_db
from app.db.models import User, ActivityLog

logger = logging.getLogger(__name__)


async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract the authenticated user from the Bearer token.
    
    Returns the User ORM object. Raises 401 if not authenticated.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = authorization[7:]
    session = get_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid session")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or deactivated")

    return user


async def log_activity(
    db: AsyncSession,
    user_id: UUID,
    event_type: str,
    description: str = "",
    metadata: dict | None = None,
) -> None:
    """Log a user activity event."""
    try:
        entry = ActivityLog(
            owner_id=user_id,
            event_type=event_type,
            description=description,
            meta=metadata,
        )
        db.add(entry)
        await db.commit()
    except Exception as e:
        logger.warning(f"Failed to log activity: {e}")
        try:
            await db.rollback()
        except Exception:
            pass

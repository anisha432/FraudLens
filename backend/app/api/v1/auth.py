"""Authentication endpoints — with activity logging."""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    hash_password, verify_password, generate_token,
    create_session, get_session, invalidate_session,
)
from app.core.deps import get_current_user, log_activity
from app.db.session import get_db
from app.db.models import User, ActivityLog

logger = logging.getLogger(__name__)
router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    confirm_password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v):
            raise ValueError("Invalid email format")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Name must be at least 2 characters")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v

    @field_validator("confirm_password")
    @classmethod
    def validate_confirm(cls, v: str) -> str:
        return v


class LoginResponse(BaseModel):
    token: str
    user: Dict[str, str]
    message: str


async def seed_demo_user(db: AsyncSession) -> None:
    result = await db.execute(select(User).where(User.email == "admin@fraudlens.io"))
    if result.scalar_one_or_none() is None:
        demo = User(
            email="admin@fraudlens.io", name="Analyst",
            password_hash=hash_password("fraudlens"), role="admin",
            is_active=True, created_at=datetime.utcnow(),
        )
        db.add(demo)
        await db.commit()
        logger.info("Demo user seeded: admin@fraudlens.io")


@router.post("/auth/login", response_model=LoginResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    email = req.email.lower().strip()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    user.last_login = datetime.utcnow()
    await db.commit()

    token = generate_token()
    create_session(token, str(user.id), user.email, user.name, user.role)

    await log_activity(db, user.id, "LOGIN", f"User {user.email} signed in")
    logger.info(f"User authenticated: {user.email}")
    return LoginResponse(
        token=token,
        user={"id": str(user.id), "email": user.email, "name": user.name, "role": user.role},
        message="Authenticated successfully",
    )


@router.post("/auth/register")
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    if req.password != req.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    email = req.email.lower().strip()
    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=email, name=req.name,
        password_hash=hash_password(req.password), role="analyst",
        is_active=True, created_at=datetime.utcnow(),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = generate_token()
    create_session(token, str(user.id), user.email, user.name, user.role)

    await log_activity(db, user.id, "REGISTER", f"New account created: {user.email}")
    return {
        "token": token,
        "user": {"id": str(user.id), "email": user.email, "name": user.name, "role": user.role},
        "message": "Account created and authenticated",
    }


@router.post("/auth/logout")
async def logout(
    user: User = Depends(get_current_user),
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Logout — invalidate token and log activity."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        invalidate_session(token)

    await log_activity(db, user.id, "LOGOUT", f"User {user.email} signed out")

    # Stop simulation for this user
    from app.api.v1.ws import stop_simulation, _user_simulations
    stop_simulation(str(user.id))
    _user_simulations.pop(str(user.id), None)

    # Clear ML workspace
    from app.ml.service import ml_service
    ml_service.clear_workspace(str(user.id))

    return {"message": "Logged out"}


@router.get("/auth/me")
async def get_current_user_endpoint(user: User = Depends(get_current_user)):
    return {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "role": user.role,
        }
    }


@router.get("/auth/activity")
async def get_activity(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user activity log — user-scoped."""
    base = ActivityLog.owner_id == user.id
    total = (await db.execute(select(func.count(ActivityLog.id)).where(base))).scalar() or 0
    result = await db.execute(
        select(ActivityLog).where(base).order_by(ActivityLog.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    entries = result.scalars().all()
    return {
        "activities": [
            {
                "id": str(a.id),
                "event_type": a.event_type,
                "description": a.description,
                "metadata": a.meta,
                "created_at": str(a.created_at) if a.created_at else None,
            } for a in entries
        ],
        "total": total,
        "page": page,
    }

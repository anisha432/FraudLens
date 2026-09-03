"""Alert management endpoints — user-scoped."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, log_activity
from app.db.session import get_db
from app.db.models import Alert, User
from app.schemas.schemas import AlertResponse, AlertListResponse, AlertUpdate

router = APIRouter()


@router.get("/alerts", response_model=AlertListResponse)
async def list_alerts(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: Optional[str] = None,
    severity: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List alerts — user-scoped."""
    query = select(Alert).where(Alert.owner_id == user.id)
    count_query = select(func.count(Alert.id)).where(Alert.owner_id == user.id)

    if status:
        query = query.where(Alert.status == status.upper())
        count_query = count_query.where(Alert.status == status.upper())
    if severity:
        query = query.where(Alert.severity == severity.upper())
        count_query = count_query.where(Alert.severity == severity.upper())

    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(Alert.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    alerts = result.scalars().all()

    return AlertListResponse(
        alerts=[
            AlertResponse(
                id=a.id, alert_id=a.alert_id, transaction_id=a.transaction_id,
                severity=a.severity, risk_score=a.risk_score,
                reasons=a.reasons, status=a.status, notes=a.notes,
                created_at=a.created_at, resolved_at=a.resolved_at,
            ) for a in alerts
        ],
        total=total,
    )


@router.patch("/alerts/{alert_id}")
async def update_alert(
    alert_id: str,
    update: AlertUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an alert's status — user-scoped."""
    result = await db.execute(
        select(Alert).where(Alert.alert_id == alert_id, Alert.owner_id == user.id)
    )
    alert = result.scalar_one_or_none()
    if not alert:
        return {"error": "Alert not found"}

    if update.status:
        alert.status = update.status.upper()
        if update.status.upper() in ("RESOLVED", "FALSE_POSITIVE"):
            alert.resolved_at = datetime.utcnow()
    if update.notes:
        alert.notes = update.notes

    await db.commit()
    await log_activity(db, user.id, "ALERT_UPDATE", f"Alert {alert_id} → {update.status}")
    return {"message": "Alert updated", "alert_id": alert_id}


@router.get("/alerts/summary")
async def alert_summary(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get alert summary — user-scoped."""
    base = Alert.owner_id == user.id
    total = (await db.execute(select(func.count(Alert.id)).where(base))).scalar() or 0
    open_count = (await db.execute(
        select(func.count(Alert.id)).where(base, Alert.status == "OPEN")
    )).scalar() or 0
    critical = (await db.execute(
        select(func.count(Alert.id)).where(base, Alert.severity == "CRITICAL")
    )).scalar() or 0
    high = (await db.execute(
        select(func.count(Alert.id)).where(base, Alert.severity == "HIGH")
    )).scalar() or 0

    return {"total": total, "open": open_count, "critical": critical, "high": high}

"""Dashboard and analytics endpoints — user-scoped."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.db.models import Transaction, Alert, User
from app.ml.service import ml_service

router = APIRouter()


@router.get("/dashboard/summary")
async def dashboard_summary(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get dashboard summary — user-scoped."""
    uid = user.id
    try:
        base = Transaction.owner_id == uid
        total = (await db.execute(select(func.count(Transaction.id)).where(base))).scalar() or 0
        fraud = (await db.execute(
            select(func.count(Transaction.id)).where(base, Transaction.prediction == "FRAUD")
        )).scalar() or 0
        fraud_rate = (fraud / total * 100) if total > 0 else 0

        fraud_amount = (await db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(base, Transaction.prediction == "FRAUD")
        )).scalar() or 0

        alert_base = Alert.owner_id == uid
        critical_alerts = (await db.execute(
            select(func.count(Alert.id)).where(alert_base, Alert.severity == "CRITICAL")
        )).scalar() or 0
        open_alerts = (await db.execute(
            select(func.count(Alert.id)).where(alert_base, Alert.status == "OPEN")
        )).scalar() or 0

        avg_risk = (await db.execute(
            select(func.coalesce(func.avg(Transaction.risk_score), 0)).where(base)
        )).scalar() or 0
        avg_fraud_prob = (await db.execute(
            select(func.coalesce(func.avg(Transaction.fraud_probability), 0)).where(base)
        )).scalar() or 0

        risk_dist = {}
        for level in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
            count = (await db.execute(
                select(func.count(Transaction.id)).where(base, Transaction.risk_level == level)
            )).scalar() or 0
            risk_dist[level] = count

        recent = await db.execute(
            select(Transaction).where(base).order_by(Transaction.created_at.desc()).limit(10)
        )
        recent_txns = recent.scalars().all()

        recent_alerts_result = await db.execute(
            select(Alert).where(alert_base).order_by(Alert.created_at.desc()).limit(10)
        )
        recent_alerts = recent_alerts_result.scalars().all()

        ws = ml_service.get_workspace(str(uid))

        return {
            "total_transactions": total,
            "fraud_transactions": fraud,
            "fraud_rate": round(fraud_rate, 2),
            "total_fraud_amount": round(float(fraud_amount), 2),
            "critical_alerts": critical_alerts,
            "open_alerts": open_alerts,
            "avg_risk_score": round(float(avg_risk), 1),
            "avg_fraud_probability": round(float(avg_fraud_prob), 4),
            "model_version": ws.model_version,
            "risk_distribution": risk_dist,
            "recent_transactions": [
                {
                    "id": str(t.id), "transaction_id": t.transaction_id,
                    "amount": t.amount, "prediction": t.prediction,
                    "fraud_probability": t.fraud_probability,
                    "risk_score": t.risk_score, "risk_level": t.risk_level,
                    "merchant": t.merchant, "location": t.location,
                    "created_at": str(t.created_at) if t.created_at else None,
                } for t in recent_txns
            ],
            "recent_alerts": [
                {
                    "id": str(a.id), "alert_id": a.alert_id,
                    "transaction_id": a.transaction_id,
                    "severity": a.severity, "status": a.status,
                    "risk_score": a.risk_score,
                    "created_at": str(a.created_at) if a.created_at else None,
                } for a in recent_alerts
            ],
        }
    except Exception as e:
        return {
            "total_transactions": 0, "fraud_transactions": 0, "fraud_rate": 0,
            "total_fraud_amount": 0, "critical_alerts": 0, "open_alerts": 0,
            "avg_risk_score": 0, "avg_fraud_probability": 0, "model_version": None,
            "risk_distribution": {}, "recent_transactions": [], "recent_alerts": [],
            "error": str(e),
        }


@router.get("/dashboard/analytics")
async def analytics(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get analytics data — user-scoped."""
    try:
        uid = user.id
        result = await db.execute(
            select(Transaction).where(
                Transaction.owner_id == uid,
                Transaction.created_at.isnot(None),
            ).order_by(Transaction.created_at)
        )
        txns = result.scalars().all()

        from collections import defaultdict
        daily = defaultdict(lambda: {"total": 0, "fraud": 0, "amount": 0})
        for t in txns:
            if t.created_at:
                day = t.created_at.strftime("%Y-%m-%d")
                daily[day]["total"] += 1
                if t.prediction == "FRAUD":
                    daily[day]["fraud"] += 1
                daily[day]["amount"] += t.amount or 0

        time_series = [{"date": k, **v} for k, v in sorted(daily.items())]

        cat_dist = defaultdict(int)
        fraud_by_cat = defaultdict(int)
        for t in txns:
            if t.category:
                cat_dist[t.category] += 1
                if t.prediction == "FRAUD":
                    fraud_by_cat[t.category] += 1

        categories = [
            {"category": k, "total": v, "fraud": fraud_by_cat.get(k, 0)}
            for k, v in sorted(cat_dist.items(), key=lambda x: -x[1])[:15]
        ]

        fraud_amounts = [t.amount for t in txns if t.prediction == "FRAUD" and t.amount]
        genuine_amounts = [t.amount for t in txns if t.prediction != "FRAUD" and t.amount]

        ml_status = ml_service.get_status(str(uid))

        return {
            "time_series": time_series,
            "categories": categories,
            "fraud_amounts": fraud_amounts[:500],
            "genuine_amounts": genuine_amounts[:500],
            "ml_status": ml_status,
        }
    except Exception as e:
        return {"time_series": [], "categories": [], "error": str(e)}

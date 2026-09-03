"""Comprehensive analytics endpoint — user-scoped."""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.db.models import Transaction, Alert, User
from app.ml.service import ml_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/analytics/executive")
async def executive_analytics(
    risk_level: Optional[str] = None,
    prediction: Optional[str] = None,
    merchant: Optional[str] = None,
    location: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Executive analytics — user-scoped."""
    uid = user.id
    try:
        base = Transaction.owner_id == uid
        query = select(Transaction).where(base)

        if risk_level:
            query = query.where(Transaction.risk_level == risk_level.upper())
        if prediction:
            query = query.where(Transaction.prediction == prediction.upper())
        if merchant:
            query = query.where(Transaction.merchant.ilike(f"%{merchant}%"))
        if location:
            query = query.where(Transaction.location.ilike(f"%{location}%"))
        if min_amount is not None:
            query = query.where(Transaction.amount >= min_amount)
        if max_amount is not None:
            query = query.where(Transaction.amount <= max_amount)

        result = await db.execute(query.order_by(Transaction.created_at.desc()))
        txns = result.scalars().all()
        total = len(txns)

        # KPIs
        fraud_count = sum(1 for t in txns if t.prediction == "FRAUD")
        fraud_rate = (fraud_count / total * 100) if total > 0 else 0
        total_value = sum(t.amount or 0 for t in txns)
        fraud_value = sum(t.amount or 0 for t in txns if t.prediction == "FRAUD")
        high_critical = sum(1 for t in txns if t.risk_level in ("HIGH", "CRITICAL"))
        avg_risk = sum(t.risk_score or 0 for t in txns) / total if total > 0 else 0
        avg_fp = sum(t.fraud_probability or 0 for t in txns) / total if total > 0 else 0

        kpi = {
            "total_transactions": total,
            "fraud_transactions": fraud_count,
            "fraud_rate": round(fraud_rate, 2),
            "high_critical_count": high_critical,
            "total_value": round(total_value, 2),
            "fraud_value": round(fraud_value, 2),
            "avg_risk_score": round(avg_risk, 2),
            "avg_fraud_probability": round(avg_fp, 4),
        }

        # Time series
        daily = defaultdict(lambda: {"total": 0, "fraud": 0, "genuine": 0, "amount": 0, "fraud_amount": 0})
        hourly = defaultdict(lambda: {"total": 0, "fraud": 0})
        for t in txns:
            if t.created_at:
                day = t.created_at.strftime("%Y-%m-%d")
                hour = t.created_at.hour
                daily[day]["total"] += 1
                daily[day]["amount"] += t.amount or 0
                hourly[hour]["total"] += 1
                if t.prediction == "FRAUD":
                    daily[day]["fraud"] += 1
                    daily[day]["fraud_amount"] += t.amount or 0
                    hourly[hour]["fraud"] += 1
                else:
                    daily[day]["genuine"] += 1

        time_series = [{"date": k, **v} for k, v in sorted(daily.items())]
        hourly_dist = [{"hour": h, "total": v["total"], "fraud": v["fraud"], "genuine": v["total"] - v["fraud"]} for h, v in sorted(hourly.items())]

        # Risk intelligence
        risk_dist = defaultdict(int)
        fp_dist = {f"{i*10}-{i*10+10}": 0 for i in range(10)}
        rs_dist = {f"{i*10}-{i*10+10}": 0 for i in range(10)}
        for t in txns:
            risk_dist[t.risk_level or "LOW"] += 1
            fp = (t.fraud_probability or 0) * 100
            fp_key = f"{min(int(fp // 10) * 10, 90)}-{min(int(fp // 10) * 10, 90) + 10}"
            fp_dist[fp_key] = fp_dist.get(fp_key, 0) + 1
            rs = t.risk_score or 0
            rs_key = f"{min(int(rs // 10) * 10, 90)}-{min(int(rs // 10) * 10, 90) + 10}"
            rs_dist[rs_key] = rs_dist.get(rs_key, 0) + 1

        # Fraud patterns
        merchant_stats = defaultdict(lambda: {"total": 0, "fraud": 0, "amount": 0})
        location_stats = defaultdict(lambda: {"total": 0, "fraud": 0, "amount": 0})
        category_stats = defaultdict(lambda: {"total": 0, "fraud": 0})
        for t in txns:
            if t.merchant:
                merchant_stats[t.merchant]["total"] += 1
                merchant_stats[t.merchant]["amount"] += t.amount or 0
                if t.prediction == "FRAUD": merchant_stats[t.merchant]["fraud"] += 1
            if t.location:
                location_stats[t.location]["total"] += 1
                location_stats[t.location]["amount"] += t.amount or 0
                if t.prediction == "FRAUD": location_stats[t.location]["fraud"] += 1
            if t.category:
                category_stats[t.category]["total"] += 1
                if t.prediction == "FRAUD": category_stats[t.category]["fraud"] += 1

        amount_ranges = {"0-50": 0, "50-100": 0, "100-500": 0, "500-1K": 0, "1K-5K": 0, "5K-10K": 0, "10K+": 0}
        fraud_amount_ranges = dict(amount_ranges)
        for t in txns:
            amt = t.amount or 0
            if amt < 50: bucket = "0-50"
            elif amt < 100: bucket = "50-100"
            elif amt < 500: bucket = "100-500"
            elif amt < 1000: bucket = "500-1K"
            elif amt < 5000: bucket = "1K-5K"
            elif amt < 10000: bucket = "5K-10K"
            else: bucket = "10K+"
            amount_ranges[bucket] += 1
            if t.prediction == "FRAUD": fraud_amount_ranges[bucket] += 1

        # Alert intelligence
        alerts_result = await db.execute(select(Alert).where(Alert.owner_id == uid))
        alerts = alerts_result.scalars().all()
        alert_severity = defaultdict(int)
        alert_status = defaultdict(int)
        for a in alerts:
            alert_severity[a.severity or "LOW"] += 1
            alert_status[a.status or "OPEN"] += 1

        # Model performance
        ws = ml_service.get_workspace(str(uid))

        # Top risk
        top_risk = sorted(txns, key=lambda t: t.risk_score or 0, reverse=True)[:20]
        merchants_list = sorted(set(t.merchant for t in txns if t.merchant))
        locations_list = sorted(set(t.location for t in txns if t.location))

        return {
            "filters_applied": {"risk_level": risk_level, "prediction": prediction, "merchant": merchant, "location": location},
            "kpi": kpi,
            "time_series": time_series,
            "risk_intelligence": {
                "risk_distribution": dict(risk_dist),
                "fraud_probability_distribution": [{"bucket": k, "count": v} for k, v in fp_dist.items()],
                "risk_score_distribution": [{"bucket": k, "count": v} for k, v in rs_dist.items()],
            },
            "fraud_patterns": {
                "by_merchant": [{"merchant": k, **v} for k, v in sorted(merchant_stats.items(), key=lambda x: -x[1]["fraud"])[:15]],
                "by_location": [{"location": k, **v} for k, v in sorted(location_stats.items(), key=lambda x: -x[1]["fraud"])[:15]],
                "by_category": [{"category": k, "total": v["total"], "fraud": v["fraud"]} for k, v in sorted(category_stats.items(), key=lambda x: -x[1]["fraud"])[:15]],
                "by_amount_range": [{"range": k, "total": amount_ranges[k], "fraud": fraud_amount_ranges[k]} for k in amount_ranges],
            },
            "temporal": {"by_hour": hourly_dist},
            "model_performance": {"status": ws.get_status(), "comparison": ws.get_model_info().get("models", [])},
            "alert_intelligence": {
                "total_alerts": len(alerts),
                "open_alerts": sum(1 for a in alerts if a.status == "OPEN"),
                "by_severity": dict(alert_severity),
                "by_status": dict(alert_status),
            },
            "top_risk_transactions": [
                {
                    "transaction_id": t.transaction_id, "amount": t.amount,
                    "merchant": t.merchant or "", "location": t.location or "",
                    "fraud_probability": round((t.fraud_probability or 0) * 100, 1),
                    "risk_score": t.risk_score or 0, "risk_level": t.risk_level or "LOW",
                    "prediction": t.prediction or "GENUINE",
                    "created_at": str(t.created_at) if t.created_at else None,
                } for t in top_risk
            ],
            "available_filters": {
                "merchants": merchants_list[:30],
                "locations": locations_list[:30],
                "risk_levels": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                "predictions": ["FRAUD", "GENUINE"],
            },
        }
    except Exception as e:
        logger.error(f"Executive analytics error: {e}")
        return {"error": str(e), "kpi": {"total_transactions": 0, "fraud_transactions": 0, "fraud_rate": 0, "high_critical_count": 0, "total_value": 0, "fraud_value": 0, "avg_risk_score": 0, "avg_fraud_probability": 0}, "time_series": [], "risk_intelligence": {"risk_distribution": {}}, "fraud_patterns": {"by_merchant": [], "by_location": []}, "temporal": {"by_hour": []}, "model_performance": {"comparison": []}, "alert_intelligence": {"total_alerts": 0, "open_alerts": 0}, "top_risk_transactions": [], "available_filters": {"merchants": [], "locations": []}}

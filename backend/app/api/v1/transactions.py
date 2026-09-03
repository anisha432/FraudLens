"""Transaction endpoints — user-scoped."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, log_activity
from app.db.session import get_db
from app.db.models import Transaction, User
from app.schemas.schemas import TransactionCreate, TransactionResponse, TransactionListResponse
from app.ml.service import ml_service

router = APIRouter()


@router.post("/transactions/predict", response_model=TransactionResponse)
async def predict_transaction(
    request: TransactionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Predict fraud for a single transaction — user-scoped."""
    result = ml_service.predict_single(str(user.id), request.model_dump())

    txn = Transaction(
        owner_id=user.id,
        transaction_id=result["transaction_id"],
        timestamp=result.get("timestamp"),
        amount=request.amount,
        user_id=request.user_id,
        merchant=request.merchant,
        category=request.category,
        location=request.location,
        device=request.device,
        payment_method=request.payment_method,
        country=request.country,
        fraud_probability=result["fraud_probability"],
        anomaly_score=result["anomaly_score"],
        risk_score=result["risk_score"],
        risk_level=result["risk_level"],
        prediction=result["prediction"],
        model_version=result["model_version"],
        created_at=datetime.utcnow(),
    )
    db.add(txn)
    await db.commit()
    await db.refresh(txn)
    await log_activity(db, user.id, "PREDICTION", f"Predicted transaction {result['transaction_id']}")
    return TransactionResponse(
        id=txn.id, transaction_id=txn.transaction_id, timestamp=txn.timestamp,
        amount=txn.amount, user_id=txn.user_id, merchant=txn.merchant,
        category=txn.category, location=txn.location, device=txn.device,
        payment_method=txn.payment_method, country=txn.country,
        fraud_probability=txn.fraud_probability, anomaly_score=txn.anomaly_score,
        risk_score=txn.risk_score, risk_level=txn.risk_level,
        prediction=txn.prediction, model_version=txn.model_version,
        created_at=txn.created_at,
    )


@router.get("/transactions", response_model=TransactionListResponse)
async def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    risk_level: Optional[str] = None,
    prediction: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    search: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List transactions — user-scoped."""
    query = select(Transaction).where(Transaction.owner_id == user.id)
    count_query = select(func.count(Transaction.id)).where(Transaction.owner_id == user.id)

    if risk_level:
        query = query.where(Transaction.risk_level == risk_level.upper())
        count_query = count_query.where(Transaction.risk_level == risk_level.upper())
    if prediction:
        query = query.where(Transaction.prediction == prediction.upper())
        count_query = count_query.where(Transaction.prediction == prediction.upper())
    if min_amount is not None:
        query = query.where(Transaction.amount >= min_amount)
        count_query = count_query.where(Transaction.amount >= min_amount)
    if max_amount is not None:
        query = query.where(Transaction.amount <= max_amount)
        count_query = count_query.where(Transaction.amount <= max_amount)
    if search:
        sf = Transaction.transaction_id.ilike(f"%{search}%")
        query = query.where(sf)
        count_query = count_query.where(sf)

    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(Transaction.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    txns = result.scalars().all()

    return TransactionListResponse(
        transactions=[
            TransactionResponse(
                id=t.id, transaction_id=t.transaction_id, timestamp=t.timestamp,
                amount=t.amount, user_id=t.user_id, merchant=t.merchant,
                category=t.category, location=t.location, device=t.device,
                payment_method=t.payment_method, country=t.country,
                fraud_probability=t.fraud_probability, anomaly_score=t.anomaly_score,
                risk_score=t.risk_score, risk_level=t.risk_level,
                prediction=t.prediction, model_version=t.model_version,
                is_simulation=t.is_simulation, created_at=t.created_at,
            ) for t in txns
        ],
        total=total, page=page, page_size=page_size,
    )


@router.get("/transactions/{transaction_id}")
async def get_transaction(
    transaction_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific transaction — user-scoped."""
    result = await db.execute(
        select(Transaction).where(
            Transaction.transaction_id == transaction_id,
            Transaction.owner_id == user.id,
        )
    )
    txn = result.scalar_one_or_none()
    if not txn:
        return {"error": "Transaction not found"}
    return {
        "id": str(txn.id), "transaction_id": txn.transaction_id,
        "timestamp": str(txn.timestamp) if txn.timestamp else None,
        "amount": txn.amount, "user_id": txn.user_id, "merchant": txn.merchant,
        "category": txn.category, "location": txn.location, "device": txn.device,
        "payment_method": txn.payment_method, "country": txn.country,
        "fraud_probability": txn.fraud_probability, "anomaly_score": txn.anomaly_score,
        "risk_score": txn.risk_score, "risk_level": txn.risk_level,
        "prediction": txn.prediction, "model_version": txn.model_version,
        "features": txn.features,
        "created_at": str(txn.created_at) if txn.created_at else None,
    }

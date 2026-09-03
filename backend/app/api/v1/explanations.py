"""Explanation endpoints — user-scoped, supports DB-stored transactions."""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.db.models import Transaction, User
from app.ml.service import ml_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/explanations/global")
async def global_explanation(user: User = Depends(get_current_user)):
    """Get global feature importance (SHAP) — user-scoped. Computes on demand if not cached."""
    explanation = ml_service.get_global_explanation(str(user.id))
    if explanation and explanation.get("features"):
        return explanation
    # Compute on demand if workspace has a model but no cached explanation
    try:
        computed = ml_service.compute_global_explanation_on_demand(str(user.id))
        if computed and computed.get("features"):
            return computed
    except Exception as e:
        logger.warning(f"Failed to compute global explanation for user {user.id}: {e}")
    return {"method": "none", "features": [], "message": "No model trained yet"}


@router.get("/explanations/{transaction_id}")
async def explain_transaction_endpoint(
    transaction_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Explain a transaction — user-scoped. Works for both training data AND DB-stored transactions."""
    ws = ml_service.get_workspace(str(user.id))

    # Step 1: Try to find in training data (fastest path)
    features = None
    for did, data in ws.datasets.items():
        if data.get("cleaned_df") is not None:
            df = data["cleaned_df"]
            col_map = data["column_map"]
            id_col = col_map.get("transaction_id")
            if id_col and id_col in df.columns:
                match = df[df[id_col].astype(str) == transaction_id]
                if len(match) > 0:
                    row = match.iloc[0]
                    features = {col: float(row[col]) for col in ws.feature_columns if col in row.index}
                    break

    # Step 2: If not in training data, look up from database (simulation transactions)
    # This is the primary path for simulation transactions
    if features is None:
        result = await db.execute(
            select(Transaction).where(
                Transaction.transaction_id == transaction_id,
                Transaction.owner_id == user.id,
            )
        )
        txn = result.scalar_one_or_none()
        if txn is None:
            return {
                "transaction_id": transaction_id,
                "method": "none",
                "contributions": [],
                "explanation_text": [f"Transaction {transaction_id} not found or access denied."],
            }

        # Priority 1: Use stored features from the transaction (most accurate)
        stored_features = _extract_stored_features(txn)
        if stored_features:
            features = stored_features
        else:
            # Priority 2: Reconstruct from DB fields (fallback)
            features = _reconstruct_features_from_transaction(txn, ws.feature_columns)

    # Step 3: Generate explanation
    if not features:
        return {
            "transaction_id": transaction_id,
            "method": "none",
            "contributions": [],
            "explanation_text": ["Could not reconstruct feature vector for this transaction."],
        }

    try:
        result = ml_service.explain_transaction_by_id(str(user.id), transaction_id, features)
    except Exception as e:
        logger.warning(f"Explanation failed for {transaction_id}: {e}")
        result = {
            "method": "builtin",
            "contributions": [{"feature": k, "value": v, "shap_value": 0.0, "direction": "unknown"} for k, v in list(features.items())[:20]],
            "explanation_text": [f"Explanation computation failed: {str(e)[:100]}"],
        }
    result["transaction_id"] = transaction_id

    # Also include prediction details from DB if available
    txn_result = await db.execute(
        select(Transaction).where(
            Transaction.transaction_id == transaction_id,
            Transaction.owner_id == user.id,
        )
    )
    txn = txn_result.scalar_one_or_none()
    if txn:
        result["fraud_probability"] = txn.fraud_probability
        result["anomaly_score"] = txn.anomaly_score
        result["risk_score"] = txn.risk_score
        result["risk_level"] = txn.risk_level
        result["prediction"] = txn.prediction

    return result


def _extract_stored_features(txn: Transaction) -> dict | None:
    """Extract feature vector from the stored features JSON on a Transaction."""
    stored = None
    if txn.features:
        if isinstance(txn.features, str):
            try:
                stored = json.loads(txn.features)
            except (json.JSONDecodeError, TypeError):
                return None
        elif isinstance(txn.features, dict):
            stored = txn.features

    if not stored or not isinstance(stored, dict):
        return None

    features = {}
    for col, val in stored.items():
        if val is not None:
            try:
                features[col] = float(val)
            except (ValueError, TypeError):
                features[col] = 0.0
        else:
            features[col] = 0.0
    return features


def _reconstruct_features_from_transaction(txn: Transaction, feature_columns: list) -> dict:
    """Reconstruct a feature vector from a database-stored transaction.
    
    This is a fallback when no stored features are available.
    Only used for legacy transactions that weren't stored with features.
    """
    features = {}

    # Time-based features
    if txn.timestamp:
        try:
            features["transaction_hour"] = float(txn.timestamp.hour)
        except (AttributeError, TypeError):
            features["transaction_hour"] = 0.0
        try:
            features["is_weekend"] = 1.0 if txn.timestamp.weekday() >= 5 else 0.0
        except (AttributeError, TypeError):
            features["is_weekend"] = 0.0
        try:
            features["is_unusual_hour"] = 1.0 if txn.timestamp.hour < 5 or txn.timestamp.hour >= 23 else 0.0
        except (AttributeError, TypeError):
            features["is_unusual_hour"] = 0.0

    # Amount-based features
    if txn.amount is not None:
        features["amount"] = float(txn.amount)
        import math
        features["log_amount"] = math.log(txn.amount + 1) if txn.amount > 0 else 0.0

    # Map known feature columns to 0 for unknown values
    for col in feature_columns:
        if col not in features:
            features[col] = 0.0

    return features


@router.get("/eda")
async def get_eda(user: User = Depends(get_current_user)):
    """Get EDA — user-scoped."""
    eda = ml_service.get_eda_data(str(user.id))
    if eda:
        return eda
    return {"message": "No EDA data available. Upload and process a dataset first."}

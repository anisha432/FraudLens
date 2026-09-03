"""Demo dataset generation endpoint — user-scoped."""
from __future__ import annotations

import asyncio
import io
import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, log_activity
from app.db.session import get_db
from app.db.models import DatasetInfo, User
from app.ml.service import ml_service
from app.ml.demo_data import generate_demo_dataset

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/demo/generate")
async def generate_demo(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a demo dataset and train models — user-scoped.
    Uses asyncio.to_thread to avoid blocking the event loop during ML training."""
    try:
        # Run blocking ML operations in a thread to avoid freezing the event loop
        def _do_training():
            df = generate_demo_dataset(n_transactions=500, fraud_rate=0.05, seed=42)
            result = ml_service.upload_dataset(str(user.id), df, "demo_transactions.csv")
            dataset_id = result["dataset_id"]
            train_result = ml_service.train(user_id=str(user.id), dataset_id=dataset_id, use_smote=True)
            return result, dataset_id, train_result

        result, dataset_id, train_result = await asyncio.to_thread(_do_training)

        # Save to DB (async)
        profile = result["profile"]
        ds = DatasetInfo(
            owner_id=user.id,
            filename="demo_transactions.csv",
            row_count=profile.get("row_count", 0),
            column_count=profile.get("column_count", 0),
            schema=profile.get("columns"),
            quality_score=profile.get("quality_score", 0),
            has_fraud_label=profile.get("has_fraud_label", False),
            target_column=profile.get("possible_target"),
            created_at=datetime.utcnow(),
        )
        db.add(ds)
        await db.commit()

        await log_activity(db, user.id, "DEMO_LOADED", "Demo dataset loaded and models trained")

        return {
            "status": "ready",
            "dataset_id": dataset_id,
            "message": "Demo dataset generated and models trained successfully",
            "profile": profile,
            "training": train_result,
        }
    except Exception as e:
        logger.exception("Demo generation error")
        return {"status": "error", "message": f"Demo generation failed: {str(e)}"}

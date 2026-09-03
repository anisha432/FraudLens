"""Upload and training endpoints — user-scoped."""
from __future__ import annotations

import asyncio
import io
import logging
from datetime import datetime

import pandas as pd
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, log_activity
from app.db.session import get_db
from app.db.models import DatasetInfo, User
from app.ml.service import ml_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload/dataset")
async def upload_dataset(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload and process a dataset — user-scoped."""
    try:
        content = await file.read()
        filename = file.filename or "uploaded.csv"

        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        elif filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(content))
        else:
            return {"error": f"Unsupported file format: {filename}"}

        # Upload to user's ML workspace (run in thread to avoid blocking event loop)
        result = await asyncio.to_thread(ml_service.upload_dataset, str(user.id), df, filename)
        dataset_id = result["dataset_id"]

        # Save to DB
        profile = result["profile"]
        ds = DatasetInfo(
            owner_id=user.id,
            filename=filename,
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

        await log_activity(db, user.id, "DATASET_UPLOADED", f"{filename} ({profile.get('row_count', 0)} rows)")

        return {
            "dataset_id": dataset_id,
            "profile": profile,
            "message": f"Dataset uploaded: {filename}",
        }
    except Exception as e:
        logger.exception("Upload error")
        return {"error": f"Upload failed: {str(e)}"}


@router.post("/train")
async def train_model(
    request: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Train models — user-scoped."""
    try:
        dataset_id = request.get("dataset_id")
        if not dataset_id:
            return {"error": "dataset_id required"}

        use_smote = request.get("use_smote", True)
        target_column = request.get("target_column")

        # Run blocking ML training in a thread to avoid freezing the event loop
        result = await asyncio.to_thread(
            ml_service.train,
            user_id=str(user.id),
            dataset_id=dataset_id,
            target_column=target_column,
            use_smote=use_smote,
        )

        await log_activity(
            db, user.id, "MODEL_TRAINED",
            f"Trained: {', '.join(result.get('models_trained', []))}",
            {"models": result.get("models_trained", []), "best": result.get("best_model")},
        )

        return result
    except Exception as e:
        logger.exception("Training error")
        return {"error": f"Training failed: {str(e)}"}


@router.get("/datasets")
async def list_datasets(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List datasets — user-scoped."""
    result = await db.execute(
        select(DatasetInfo).where(DatasetInfo.owner_id == user.id).order_by(DatasetInfo.created_at.desc())
    )
    datasets = result.scalars().all()
    return {
        "datasets": [
            {
                "dataset_id": str(d.id),
                "filename": d.filename,
                "row_count": d.row_count,
                "column_count": d.column_count,
                "has_fraud_label": d.has_fraud_label,
                "quality_score": d.quality_score,
            } for d in datasets
        ]
    }

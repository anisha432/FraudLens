"""Model endpoints — user-scoped."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from app.core.deps import get_current_user
from app.db.models import User
from app.ml.service import ml_service

router = APIRouter()


@router.get("/models")
async def get_models(user: User = Depends(get_current_user)):
    """Get model info — user-scoped."""
    return ml_service.get_model_info(str(user.id))


@router.get("/models/compare")
async def model_comparison(user: User = Depends(get_current_user)):
    """Get model comparison — user-scoped."""
    return {"models": ml_service.get_comparison(str(user.id))}


@router.get("/models/feature-importance")
async def feature_importance(user: User = Depends(get_current_user)):
    """Get feature importance — user-scoped."""
    return ml_service.get_feature_importance(str(user.id))


@router.post("/models/threshold")
async def threshold_analysis(request: dict, user: User = Depends(get_current_user)):
    """Get threshold analysis — user-scoped."""
    results = ml_service.get_threshold_analysis(str(user.id))
    return {"thresholds": results}

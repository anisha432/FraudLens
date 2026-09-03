"""Health check endpoints."""
from __future__ import annotations

import time
from fastapi import APIRouter

from app.core.config import get_settings
from app.ml.service import ml_service

router = APIRouter()
settings = get_settings()
_start_time = time.time()


@router.get("/api/v1/health")
async def health_check():
    """Health check endpoint."""
    uptime_secs = time.time() - _start_time
    hours = int(uptime_secs // 3600)
    minutes = int((uptime_secs % 3600) // 60)
    seconds = int(uptime_secs % 60)
    uptime = f"{hours}h {minutes}m {seconds}s"

    ml_status = ml_service.get_global_status()

    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "database": "connected",
        "models_loaded": ml_status["models_loaded"],
        "uptime": uptime,
    }

"""FastAPI Application - Fraud Detection Platform."""
from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.api.v1 import transactions, alerts, models, dashboard, upload, health, explanations, ws, demo, auth, analytics
from app.db.session import init_db, close_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()
start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    logger.info("Starting Fraud Detection Platform...")
    try:
        await init_db()
        logger.info("Database initialized")
        # Seed the demo user
        from app.db.session import async_session_factory
        if async_session_factory:
            async with async_session_factory() as db:
                from app.api.v1.auth import seed_demo_user
                await seed_demo_user(db)
    except Exception as e:
        logger.warning(f"Database init failed (will use in-memory): {e}")
    yield
    logger.info("Shutting down...")
    try:
        await close_db()
    except Exception:
        pass


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Real-Time Fraud & Anomaly Detection Intelligence Platform",
    lifespan=lifespan,
)

# CORS — use configured origins in production, allow all in DEBUG
if settings.DEBUG:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, prefix="/api/v1", tags=["Auth"])
app.include_router(upload.router, prefix="/api/v1", tags=["Upload"])
app.include_router(transactions.router, prefix="/api/v1", tags=["Transactions"])
app.include_router(alerts.router, prefix="/api/v1", tags=["Alerts"])
app.include_router(models.router, prefix="/api/v1", tags=["Models"])
app.include_router(dashboard.router, prefix="/api/v1", tags=["Dashboard"])
app.include_router(explanations.router, prefix="/api/v1", tags=["Explanations"])
app.include_router(demo.router, prefix="/api/v1", tags=["Demo"])
app.include_router(ws.router, tags=["WebSocket"])
app.include_router(analytics.router, prefix="/api/v1", tags=["Analytics"])


@app.get("/")
async def root():
    return {"message": "Fraud Detection Platform API", "version": settings.APP_VERSION}


@app.get("/api/v1/start-time")
async def get_start_time():
    return {"start_time": start_time}

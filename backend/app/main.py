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
        # Seed the demo user
        from app.db.session import async_session_factory
        if async_session_factory:
            async with async_session_factory() as db:
                from app.api.v1.auth import seed_demo_user
                await seed_demo_user(db)
        logger.info("Database initialized")
    except Exception as e:
        if settings.DEBUG:
            logger.warning(f"Database startup incomplete in DEBUG mode ({e}); continuing")
        else:
            logger.error(
                "Database initialization FAILED (DEBUG=false). "
                "Refusing to start without a working production database. "
                "Check DATABASE_URL / DATABASE_URL_SYNC and retry."
            )
            raise
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

# CORS — allow all origins in DEBUG (local development only). In production
# the allowlist is never "*" because the app uses authentication: it is the
# configured CORS_ORIGINS (settings/env) PLUS the FraudLens production frontend
# origin below, which is always allowed so a missing or mistyped CORS_ORIGINS
# on the deployment can never break browser requests — e.g. the
# POST /api/v1/auth/register preflight (OPTIONS) must return
# Access-Control-Allow-Origin for the deployed frontend.
PROD_FRONTEND_ORIGINS: tuple[str, ...] = ("https://fraudlens-frontend-1irz.onrender.com",)


def resolve_cors_origins(*, debug: bool, configured_origins: list[str]) -> list[str]:
    """Return the CORSMiddleware ``allow_origins`` list for the current mode.

    DEBUG:       ["*"] (development convenience; behavior unchanged).
    Production:  the configured origins plus the FraudLens production frontend,
                 de-duplicated and order-preserving. The frontend origin is
                 merged here rather than taken from settings alone so that the
                 CORS_ORIGINS env var can extend — but never remove — it.
    """
    if debug:
        return ["*"]
    merged: list[str] = []
    for origin in [*configured_origins, *PROD_FRONTEND_ORIGINS]:
        if origin not in merged:
            merged.append(origin)
    return merged


_cors_origins = resolve_cors_origins(
    debug=settings.DEBUG, configured_origins=settings.CORS_ORIGINS
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info("CORS allow_origins (DEBUG=%s): %s", settings.DEBUG, _cors_origins)

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

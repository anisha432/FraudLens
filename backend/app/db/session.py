"""Database session management with fallback to SQLite."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Lazy-initialized globals
engine = None
async_session_factory = None
sync_engine = None
SyncSessionLocal = None
_db_available = False


def _init_engines():
    """Initialize database engines. Falls back to SQLite if PostgreSQL unavailable."""
    global engine, async_session_factory, sync_engine, SyncSessionLocal, _db_available

    from app.core.config import get_settings
    settings = get_settings()

    # Try PostgreSQL first, fall back to SQLite
    db_url = settings.DATABASE_URL
    db_url_sync = settings.DATABASE_URL_SYNC

    try:
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import create_engine

        # Try asyncpg first
        try:
            engine = create_async_engine(db_url, echo=settings.DEBUG, pool_pre_ping=True)
            async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            sync_engine = create_engine(db_url_sync, echo=False, pool_pre_ping=True)
            SyncSessionLocal = sessionmaker(bind=sync_engine)
            _db_available = True
            logger.info(f"Connected to PostgreSQL: {db_url.split('@')[-1] if '@' in db_url else db_url}")
            return
        except Exception as e:
            logger.warning(f"PostgreSQL unavailable ({e}), falling back to SQLite")
            engine = None

        # Fallback to SQLite
        sqlite_url = "sqlite+aiosqlite:///./fraud_detection.db"
        sqlite_sync_url = "sqlite:///./fraud_detection.db"
        engine = create_async_engine(sqlite_url, echo=settings.DEBUG)
        async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        sync_engine = create_engine(sqlite_sync_url, echo=False)
        SyncSessionLocal = sessionmaker(bind=sync_engine)
        _db_available = True
        logger.info("Using SQLite fallback database")

    except Exception as e:
        logger.error(f"Failed to initialize any database: {e}")
        _db_available = False


def _ensure_engines():
    """Lazily initialize engines on first use."""
    if engine is None:
        _init_engines()


async def get_db():
    """Dependency for FastAPI routes."""
    _ensure_engines()
    if async_session_factory is None:
        raise RuntimeError("Database not available")
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialize database tables."""
    _ensure_engines()
    if engine is None:
        return
    try:
        from app.db.models import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        logger.warning(f"DB table creation failed: {e}")


async def close_db():
    """Close database connections."""
    if engine is not None:
        try:
            await engine.dispose()
        except Exception:
            pass


def init_db_sync():
    """Initialize database tables synchronously."""
    _ensure_engines()
    if sync_engine is not None:
        from app.db.models import Base
        Base.metadata.create_all(bind=sync_engine)

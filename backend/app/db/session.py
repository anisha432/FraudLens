"""Database session management.

Database selection
------------------
* PostgreSQL is used whenever ``DATABASE_URL`` points to PostgreSQL (e.g. Neon
  on Render). The async engine always uses **asyncpg** — a plain
  ``postgresql://`` (psycopg2) URL is never passed to ``create_async_engine``.
* SQLite is used for local development only: either because it is the default
  (no ``DATABASE_URL`` configured) or because a PostgreSQL configuration
  failed while ``DEBUG=true``.
* When ``DEBUG=false`` (production), a PostgreSQL configuration or connection
  failure is a hard startup error. The app must not silently fall back to
  SQLite in production.
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

# Lazy-initialized globals
engine = None
async_session_factory = None
sync_engine = None
SyncSessionLocal = None

_backend = None  # "sqlite" | "postgresql" | None — engine actually in use

_DEFAULT_SQLITE_URL = "sqlite+aiosqlite:///./fraud_detection.db"
_DEFAULT_SQLITE_SYNC_URL = "sqlite:///./fraud_detection.db"

# Startup must never hang on an unreachable PostgreSQL server (e.g. Neon on
# Render): uvicorn runs the lifespan *before* it binds the listen port, so a
# blocked connect keeps the service in "no open ports" state and the platform
# reports a port-scan timeout instead of the real database error. Bound every
# startup wait so the actual failure surfaces quickly and loudly.
_POSTGRES_CONNECT_TIMEOUT_SECONDS = 10
_DB_INIT_TIMEOUT_SECONDS = 30

# Query parameters that may safely remain on a PostgreSQL URL handed to
# ``create_async_engine``. SQLAlchemy's asyncpg dialect forwards *every* URL
# query parameter as a keyword argument to ``asyncpg.connect()``, and asyncpg
# only accepts a fixed set of keywords. libpq-only parameters found on managed
# PostgreSQL connection strings (e.g. Neon's ``channel_binding``) have no
# asyncpg equivalent and would raise ``TypeError: connect() got an unexpected
# keyword argument ...`` at connect time, so anything outside this set is
# stripped during normalization.
_ASYNCPG_URL_QUERY_PARAMS = frozenset({
    # asyncpg.connect() keyword parameters.
    "ssl",
    "timeout",
    "command_timeout",
    "statement_cache_size",
    "max_cached_statement_lifetime",
    "max_cacheable_statement_size",
    "min_ssl_protocol_version",
    "max_ssl_protocol_version",
    "target_session_attrs",
    # SQLAlchemy asyncpg-dialect options (consumed by the dialect, not asyncpg).
    "prepared_statement_cache_size",
    "async_fallback",
    # SQLAlchemy asyncpg multihost syntax (``?host=HostA:5432&host=HostB:5432``).
    "host",
})


def _is_sqlite_url(url: str | None) -> bool:
    """Return True when a database URL points at SQLite."""
    if not url:
        return False
    drivername = url.split("://", 1)[0].strip().lower()
    return drivername == "sqlite" or drivername.startswith("sqlite+")


def normalize_async_database_url(url: str) -> str:
    """Return a URL that is safe to pass to ``create_async_engine``.

    * SQLite URLs pass through unchanged.
    * Any PostgreSQL URL is forced onto the **asyncpg** driver — a plain
      ``postgresql://`` (or ``postgres://``) URL must never reach the async
      engine, since SQLAlchemy would load the synchronous psycopg2 driver and
      raise "The asyncio extension requires an async driver".
    * The libpq ``sslmode`` query parameter found on Neon / managed PostgreSQL
      connection strings is translated to the ``ssl`` parameter that the
      asyncpg dialect understands (asyncpg has no ``sslmode`` kwarg).
    * Remaining query parameters are filtered to the set asyncpg / the asyncpg
      dialect actually accepts. libpq-only parameters (e.g. ``channel_binding``,
      which asyncpg does not implement) are otherwise forwarded verbatim to
      ``asyncpg.connect`` by the dialect and raise ``TypeError`` at connect
      time — exactly the production failure this filter prevents.
    """
    if _is_sqlite_url(url):
        return url

    parsed = make_url(url).set(drivername="postgresql+asyncpg")
    query = dict(parsed.query)
    sslmode = query.pop("sslmode", None)
    if sslmode is not None and "ssl" not in query:
        query["ssl"] = sslmode
    query = {
        key: value
        for key, value in query.items()
        if key in _ASYNCPG_URL_QUERY_PARAMS
    }
    parsed = parsed.set(query=query)
    return parsed.render_as_string(hide_password=False)


def normalize_sync_database_url(url: str) -> str:
    """Return a URL safe for a synchronous ``create_engine`` call.

    * SQLite URLs pass through unchanged.
    * PostgreSQL URLs are forced onto the psycopg2 driver (the default
      PostgreSQL driver), which natively understands ``sslmode``.
    """
    if _is_sqlite_url(url):
        return url

    parsed = make_url(url).set(drivername="postgresql+psycopg2")
    return parsed.render_as_string(hide_password=False)


def _host_of(url: str) -> str:
    """Best-effort host:port description — never includes credentials."""
    try:
        parsed = make_url(url)
        return f"{parsed.host or '?'}:{parsed.port or 5432}"
    except Exception:
        return (url.split("@")[-1].split("/")[0] or url) if "@" in url else url


def _configure_sqlite(settings, *, fallback: bool) -> None:
    """Configure the engines to use SQLite (local development only)."""
    global engine, async_session_factory, sync_engine, SyncSessionLocal, _backend

    # Release any previously created engine (e.g. a failed PostgreSQL engine).
    # Note: AsyncEngine.dispose() is a coroutine, so dispose the underlying
    # sync engine here; async callers dispose properly before reconfiguring.
    if engine is not None:
        try:
            engine.sync_engine.dispose()
        except Exception:
            pass
        engine = None
    if sync_engine is not None:
        try:
            sync_engine.dispose()
        except Exception:
            pass
        sync_engine = None
        SyncSessionLocal = None

    sqlite_url = _DEFAULT_SQLITE_URL
    sqlite_sync_url = _DEFAULT_SQLITE_SYNC_URL
    if not fallback:
        # Honor an explicitly configured SQLite URL (custom local DB path).
        if _is_sqlite_url(settings.DATABASE_URL):
            sqlite_url = settings.DATABASE_URL
        if _is_sqlite_url(settings.DATABASE_URL_SYNC):
            sqlite_sync_url = settings.DATABASE_URL_SYNC

    engine = create_async_engine(sqlite_url, echo=settings.DEBUG)
    async_session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    _backend = "sqlite"
    if fallback:
        logger.warning(
            "Falling back to SQLite (%s) — local development only.", sqlite_url
        )
    else:
        logger.info("Using SQLite database for local development: %s", sqlite_url)


def _init_engines() -> None:
    """Initialize the async engine based on the configured ``DATABASE_URL``."""
    global engine, async_session_factory, _backend

    from app.core.config import get_settings
    settings = get_settings()

    db_url = (settings.DATABASE_URL or "").strip()
    if _is_sqlite_url(db_url):
        _configure_sqlite(settings, fallback=False)
        return

    try:
        async_url = normalize_async_database_url(db_url)
        connect_args: dict[str, object] = {}
        if "timeout" not in make_url(async_url).query:
            # asyncpg's default connect timeout is 60s, and a SYN-blackholed
            # host (suspended Neon compute, firewall drop, DNS hang) blocks even
            # longer — long enough for the platform's port scan to time out
            # first. Bound it unless the URL explicitly sets a timeout.
            connect_args["timeout"] = _POSTGRES_CONNECT_TIMEOUT_SECONDS
        engine = create_async_engine(
            async_url,
            echo=settings.DEBUG,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
        async_session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        _backend = "postgresql"
        logger.info("Configured PostgreSQL engine (asyncpg) at %s", _host_of(async_url))
    except Exception as e:
        if settings.DEBUG:
            logger.warning(
                "PostgreSQL unavailable in DEBUG mode (%s); falling back to SQLite", e
            )
            _configure_sqlite(settings, fallback=True)
            return
        logger.error(
            "PostgreSQL engine configuration FAILED (DEBUG=false). "
            "Refusing to start with a SQLite fallback in production."
        )
        raise RuntimeError(
            f"PostgreSQL engine could not be initialized: {e}. "
            f"Check DATABASE_URL ({_host_of(db_url)})."
        ) from e


def _ensure_engines() -> None:
    """Lazily initialize engines on first use."""
    if engine is None:
        _init_engines()


def _ensure_sync_engine() -> None:
    """Lazily create the synchronous engine — only used where sync DB access
    is explicitly required (e.g. ``init_db_sync``). psycopg2 is therefore
    never loaded during normal async operation."""
    global sync_engine, SyncSessionLocal

    if sync_engine is not None:
        return

    from app.core.config import get_settings
    settings = get_settings()

    db_url_sync = (settings.DATABASE_URL_SYNC or "").strip()
    if not db_url_sync:
        db_url_sync = settings.DATABASE_URL

    if _backend == "sqlite" or _is_sqlite_url(db_url_sync):
        url = db_url_sync if _is_sqlite_url(db_url_sync) else _DEFAULT_SQLITE_SYNC_URL
        sync_engine = create_engine(url, echo=False)
    else:
        url = normalize_sync_database_url(db_url_sync)
        sync_engine = create_engine(url, echo=False, pool_pre_ping=True)
    SyncSessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=False)


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


async def init_db() -> None:
    """Initialize database tables.

    Performs a real connection round-trip (``create_all``). In production
    (``DEBUG=false``) any failure is re-raised so startup stops loudly; in
    DEBUG mode a PostgreSQL that cannot be reached falls back to SQLite to
    preserve the local development workflow.
    """
    _ensure_engines()
    if engine is None:
        raise RuntimeError("Database not available: no engine could be initialized")

    from app.core.config import get_settings
    settings = get_settings()

    from app.db.models import Base

    try:
        try:
            async with asyncio.timeout(_DB_INIT_TIMEOUT_SECONDS):
                async with engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
        except TimeoutError:
            raise RuntimeError(
                f"Database initialization timed out: the configured database "
                f"({_host_of(settings.DATABASE_URL or '')}) did not accept a "
                f"connection in time "
                f"(connect timeout {_POSTGRES_CONNECT_TIMEOUT_SECONDS}s, "
                f"init timeout {_DB_INIT_TIMEOUT_SECONDS}s). Check that it is "
                f"awake/reachable and DATABASE_URL is correct."
            ) from None
    except Exception as e:
        if settings.DEBUG and _backend == "postgresql":
            logger.warning(
                "PostgreSQL unreachable in DEBUG mode (%s); falling back to SQLite", e
            )
            await engine.dispose()
            _configure_sqlite(settings, fallback=True)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        else:
            raise RuntimeError(
                f"Database initialization failed: {e}. "
                f"Check that the configured database is reachable "
                f"({_host_of(settings.DATABASE_URL or '')})."
            ) from e


async def close_db() -> None:
    """Close database connections."""
    if engine is not None:
        try:
            await engine.dispose()
        except Exception:
            pass
    if sync_engine is not None:
        try:
            sync_engine.dispose()
        except Exception:
            pass


def init_db_sync() -> None:
    """Initialize database tables synchronously (sync engine only)."""
    _ensure_sync_engine()
    if sync_engine is None:
        raise RuntimeError("Synchronous database engine not available")
    from app.db.models import Base
    Base.metadata.create_all(bind=sync_engine)

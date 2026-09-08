"""Authentication and database configuration tests.

Covers the two production-critical fixes:

1. PostgreSQL async driver handling — ``DATABASE_URL`` is normalized to the
   asyncpg driver before it ever reaches ``create_async_engine``, Neon's
   ``sslmode`` parameter is translated to asyncpg's ``ssl`` parameter,
   libpq-only parameters such as ``channel_binding`` are stripped so they
   never reach ``asyncpg.connect()``, and the app refuses to silently fall
   back to SQLite when ``DEBUG=false``.
2. passlib/bcrypt compatibility — bcrypt is pinned below 4.1 (see
   ``backend/requirements.txt``) and registration rejects passwords longer
   than the 72-byte bcrypt limit up front.

Also exercises the login / register / logout flow, demo credentials and user
isolation against a throwaway SQLite database (see ``conftest.py``).
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url


# --------------------------------------------------------------------------
# WebSocket auth: valid/missing/invalid/expired token
# --------------------------------------------------------------------------


class TestWebSocketAuth:
    def test_websocket_accepts_valid_token(self, client):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@fraudlens.io", "password": "fraudlens"},
        )
        assert resp.status_code == 200, resp.text
        token = resp.json()["token"]

        with client.websocket_connect(f"/ws/live?token={token}") as ws:
            assert ws.receive_text()  # may be the initial heartbeat once the app enables it
            # A valid token is accepted: the connection was upgraded.

    def test_websocket_rejects_missing_token(self, client):
        with pytest.raises(Exception) as exc_info:
            with client.websocket_connect("/ws/live"):
                pass
        # FastAPI's TestClient raises when the server closes the connection
        # (including a custom close code/reason).
        assert exc_info.value is not None

    def test_websocket_rejects_empty_token(self, client):
        with pytest.raises(Exception) as exc_info:
            with client.websocket_connect("/ws/live?token="):
                pass
        assert exc_info.value is not None

    def test_websocket_rejects_unknown_token(self, client):
        with pytest.raises(Exception) as exc_info:
            with client.websocket_connect(
                "/ws/live?token=unknown-token-that-was-never-issued"
            ):
                pass
        assert exc_info.value is not None

    def test_websocket_rejects_invalidated_token(self, client):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@fraudlens.io", "password": "fraudlens"},
        )
        assert resp.status_code == 200, resp.text
        token = resp.json()["token"]

        # Invalidate the token exactly as logout does.
        from app.core.auth import invalidate_session
        invalidated = invalidate_session(token)
        assert invalidated is True

        with pytest.raises(Exception) as exc_info:
            with client.websocket_connect(f"/ws/live?token={token}"):
                pass
        assert exc_info.value is not None

from app.main import app


# --------------------------------------------------------------------------
# PostgreSQL URL normalization (asyncpg / psycopg2)
# --------------------------------------------------------------------------

NEON_URL = "postgresql://fraud_user:secret@ep-xyz-123.us-east-2.aws.neon.tech/neondb?sslmode=require"


def _import_db_session():
    # Imported lazily so engine globals are only touched by the tests that
    # need them; the FastAPI lifespan tests initialize the real (SQLite)
    # engine independently.
    import app.db.session as s
    return s


class TestAsyncUrlNormalization:
    def test_neon_url_uses_asyncpg_and_translates_sslmode(self):
        s = _import_db_session()
        result = s.normalize_async_database_url(NEON_URL)
        parsed = make_url(result)

        assert parsed.drivername == "postgresql+asyncpg"
        # The async engine must never be handed a psycopg2/plain-postgres URL.
        assert "psycopg2" not in parsed.drivername
        assert parsed.host == "ep-xyz-123.us-east-2.aws.neon.tech"
        assert parsed.database == "neondb"
        assert parsed.password == "secret"
        # asyncpg has no sslmode kwarg; the asyncpg dialect forwards query
        # params to asyncpg.connect(), so sslmode must become ssl.
        assert "sslmode" not in parsed.query
        assert parsed.query.get("ssl") == "require"

    def test_channel_binding_and_unknown_libpq_params_are_stripped(self):
        # Neon-style pooled URL carrying libpq-only parameters. asyncpg does
        # not implement channel binding (or accept libpq's other connection
        # keywords), and the asyncpg dialect forwards every query param as an
        # asyncpg.connect() kwarg — a leftover channel_binding previously
        # crashed startup with "connect() got an unexpected keyword argument
        # 'channel_binding'".
        s = _import_db_session()
        url = (
            "postgresql://fraud_user:secret@ep-xyz-123-pooler.us-east-2.aws.neon.tech"
            "/neondb?sslmode=require&channel_binding=require&application_name=fraudlens"
        )
        parsed = make_url(s.normalize_async_database_url(url))

        assert parsed.drivername == "postgresql+asyncpg"
        assert "channel_binding" not in parsed.query
        assert "application_name" not in parsed.query
        # sslmode is still translated to asyncpg's ssl parameter: TLS is kept.
        assert parsed.query.get("ssl") == "require"

    def test_supported_asyncpg_query_params_are_kept(self):
        s = _import_db_session()
        url = (
            "postgresql+asyncpg://user:pass@db.example.com/db"
            "?ssl=require&timeout=30&command_timeout=5&prepared_statement_cache_size=0"
        )
        query = dict(make_url(s.normalize_async_database_url(url)).query)
        assert query == {
            "ssl": "require",
            "timeout": "30",
            "command_timeout": "5",
            "prepared_statement_cache_size": "0",
        }

    def test_plain_postgres_url_gets_asyncpg_driver(self):
        s = _import_db_session()
        result = s.normalize_async_database_url(
            "postgresql://user:pass@db.example.com:5432/fraud_detection"
        )
        parsed = make_url(result)
        assert parsed.drivername == "postgresql+asyncpg"
        assert parsed.host == "db.example.com"
        assert parsed.port == 5432
        assert parsed.query == {}

    def test_short_postgres_scheme_is_normalized(self):
        s = _import_db_session()
        result = s.normalize_async_database_url(
            "postgres://user:pass@db.example.com:5432/db"
        )
        assert make_url(result).drivername == "postgresql+asyncpg"

    def test_already_asyncpg_url_is_idempotent(self):
        s = _import_db_session()
        result = s.normalize_async_database_url(
            "postgresql+asyncpg://user:pass@db.example.com/db?ssl=require"
        )
        parsed = make_url(result)
        assert parsed.drivername == "postgresql+asyncpg"
        assert parsed.query.get("ssl") == "require"

    def test_sqlite_url_passes_through_unchanged(self):
        s = _import_db_session()
        url = "sqlite+aiosqlite:///./fraud_detection.db"
        assert s.normalize_async_database_url(url) == url


class TestSyncUrlNormalization:
    def test_neon_url_uses_psycopg2_and_keeps_sslmode(self):
        s = _import_db_session()
        result = s.normalize_sync_database_url(NEON_URL)
        parsed = make_url(result)
        assert parsed.drivername == "postgresql+psycopg2"
        # psycopg2 (libpq) understands sslmode natively.
        assert parsed.query.get("sslmode") == "require"

    def test_sqlite_url_passes_through_unchanged(self):
        s = _import_db_session()
        url = "sqlite:///./fraud_detection.db"
        assert s.normalize_sync_database_url(url) == url


# --------------------------------------------------------------------------
# PostgreSQL schema compatibility (foreign keys must target unique columns)
# --------------------------------------------------------------------------

class TestPostgresSchemaCompat:
    def test_all_foreign_keys_reference_unique_columns(self):
        """PostgreSQL rejects a FK whose target is not a primary key or a
        unique column (SQLSTATE 42830: "there is no unique constraint matching
        given keys for referenced table"), whereas SQLite silently allows it.
        Every FK in the metadata must therefore target a unique column so the
        schema created by ``create_all`` is valid on both backends."""
        from sqlalchemy import UniqueConstraint

        from app.db.models import Base

        problems = []
        for table in Base.metadata.sorted_tables:
            for fk in table.foreign_key_constraints:
                for element in fk.elements:
                    target = element.column
                    is_pk = target.primary_key
                    covered = target.unique or any(
                        target.name in {c.name for c in uc.columns}
                        for uc in target.table.constraints
                        if isinstance(uc, UniqueConstraint)
                    )
                    if not (is_pk or covered):
                        problems.append(
                            f"{table.name}.{element.parent.name} -> "
                            f"{target.table.name}.{target.name}"
                        )
        assert problems == [], (
            "Foreign keys must reference PK/unique columns for PostgreSQL: "
            + ", ".join(problems)
        )

    def test_alerts_transaction_id_is_not_a_foreign_key(self):
        """alerts.transaction_id references the non-unique business key
        transactions.transaction_id, which PostgreSQL will not accept as an FK
        target. The column is kept (indexed) but the FK constraint is dropped;
        only the users.id FK remains."""
        from app.db.models import Alert

        fk_targets = sorted(fk.target_fullname for fk in Alert.__table__.foreign_keys)
        assert fk_targets == ["users.id"]


# --------------------------------------------------------------------------
# No silent SQLite fallback in production
# --------------------------------------------------------------------------

class _StubSettings:
    def __init__(self, debug: bool, db_url: str, db_url_sync: str = ""):
        self.DEBUG = debug
        self.DATABASE_URL = db_url
        self.DATABASE_URL_SYNC = db_url_sync


def _patch_settings(monkeypatch, settings):
    import app.core.config as config
    # session.py resolves get_settings via ``from app.core.config import ...``
    # inside its functions, so patching the config module is sufficient.
    monkeypatch.setattr(config, "get_settings", lambda: settings)


def _restore_engine_globals(s):
    for name in ("engine", "async_session_factory", "sync_engine", "SyncSessionLocal", "_backend"):
        setattr(s, name, None)


class TestProductionFailFast:
    def test_production_engine_failure_raises_no_sqlite_fallback(self, monkeypatch):
        s = _import_db_session()
        _patch_settings(monkeypatch, _StubSettings(debug=False, db_url=NEON_URL))
        monkeypatch.setattr(s, "create_async_engine", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))

        def _forbid_sqlite_fallback(*a, **k):
            raise AssertionError("SQLite fallback must NOT happen in production (DEBUG=false)")

        monkeypatch.setattr(s, "_configure_sqlite", _forbid_sqlite_fallback)
        try:
            with pytest.raises(RuntimeError, match="PostgreSQL"):
                s._init_engines()
        finally:
            _restore_engine_globals(s)
        assert s.engine is None

    def test_debug_mode_falls_back_to_sqlite(self, monkeypatch):
        s = _import_db_session()
        _patch_settings(monkeypatch, _StubSettings(debug=True, db_url=NEON_URL))
        real_create_async_engine = s.create_async_engine
        calls = {"n": 0}

        def _flaky_async_engine(*args, **kwargs):
            # First attempt (PostgreSQL engine) fails; the DEBUG-mode fallback
            # to SQLite must still be able to create its own engine.
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("driver unavailable")
            return real_create_async_engine(*args, **kwargs)

        monkeypatch.setattr(s, "create_async_engine", _flaky_async_engine)
        try:
            # Must NOT raise in DEBUG mode.
            s._init_engines()
            assert calls["n"] == 2
            assert s._backend == "sqlite"
            assert s.async_session_factory is not None
            assert s.engine is not None
            assert "sqlite" in s.engine.url.drivername
        finally:
            _restore_engine_globals(s)

    def test_configured_sqlite_is_used_for_local_development(self, monkeypatch):
        s = _import_db_session()
        url = "sqlite+aiosqlite:///./local_dev_only.db"
        _patch_settings(monkeypatch, _StubSettings(debug=True, db_url=url, db_url_sync="sqlite:///./local_dev_only.db"))
        try:
            s._init_engines()
            assert s._backend == "sqlite"
            assert s.engine.url.drivername == "sqlite+aiosqlite"
        finally:
            _restore_engine_globals(s)


# --------------------------------------------------------------------------
# Startup timeout guards (an unreachable DB must fail fast, not hang startup)
# --------------------------------------------------------------------------

# uvicorn runs the FastAPI lifespan *before* it binds the listen port, so a
# startup that blocks forever on an unreachable PostgreSQL (suspended Neon
# compute, firewall drop, TLS handshake hang) keeps the service in a
# "no open ports" state and the platform reports a port-scan timeout instead
# of the real error. The engine carries a bounded connect timeout and init_db
# wraps its round-trip in a hard timeout; these tests pin both.


class _HangingBeginEngine:
    """Stand-in async engine whose begin() blocks longer than the init guard."""

    def __init__(self, hang_seconds: float):
        self._hang = hang_seconds
        self.disposed = False

    def begin(self):
        return self

    async def __aenter__(self):
        await asyncio.sleep(self._hang)
        raise AssertionError("connect should have been cancelled by the timeout guard")

    async def __aexit__(self, *exc):
        return False

    async def dispose(self):
        self.disposed = True


class TestStartupTimeoutGuard:
    def test_postgres_engine_gets_bounded_connect_timeout(self, monkeypatch):
        """The asyncpg engine must be created with an explicit connect timeout
        so a SYN-blackholed database host cannot block startup indefinitely."""
        s = _import_db_session()
        _patch_settings(monkeypatch, _StubSettings(debug=False, db_url=NEON_URL))
        captured = {}

        def _fake_engine(url, **kwargs):
            captured["url"] = str(url)
            captured["kwargs"] = kwargs
            return _HangingBeginEngine(0)

        monkeypatch.setattr(s, "create_async_engine", _fake_engine)
        try:
            s._init_engines()
            assert captured["kwargs"]["connect_args"] == {
                "timeout": s._POSTGRES_CONNECT_TIMEOUT_SECONDS
            }
        finally:
            _restore_engine_globals(s)

    def test_url_timeout_param_is_respected_over_default(self, monkeypatch):
        s = _import_db_session()
        url = NEON_URL + "&timeout=45"
        _patch_settings(monkeypatch, _StubSettings(debug=False, db_url=url))
        captured = {}

        def _fake_engine(url, **kwargs):
            captured["kwargs"] = kwargs
            return _HangingBeginEngine(0)

        monkeypatch.setattr(s, "create_async_engine", _fake_engine)
        try:
            s._init_engines()
            # An explicit URL timeout must not be overridden by the default.
            assert captured["kwargs"]["connect_args"] == {}
        finally:
            _restore_engine_globals(s)

    def test_init_db_hang_fails_fast_with_clear_error(self, monkeypatch):
        s = _import_db_session()
        _patch_settings(monkeypatch, _StubSettings(debug=False, db_url=NEON_URL))
        monkeypatch.setattr(s, "_DB_INIT_TIMEOUT_SECONDS", 0.4)
        fake = _HangingBeginEngine(5)  # hangs far longer than the 0.4s guard
        monkeypatch.setattr(s, "create_async_engine", lambda *a, **k: fake)

        started = time.monotonic()
        try:
            with pytest.raises(RuntimeError, match="init timeout 0.4s"):
                asyncio.run(s.init_db())
            assert time.monotonic() - started < 3, "init_db must fail fast, not hang"
        finally:
            _restore_engine_globals(s)

    def test_debug_mode_timeout_still_falls_back_to_sqlite(self, monkeypatch):
        """The local-development workflow is preserved: in DEBUG mode a hung
        PostgreSQL still falls back to SQLite instead of failing."""
        s = _import_db_session()
        _patch_settings(monkeypatch, _StubSettings(debug=True, db_url=NEON_URL))
        monkeypatch.setattr(s, "_DB_INIT_TIMEOUT_SECONDS", 0.4)
        real_create_async_engine = s.create_async_engine
        calls = {"n": 0}

        def _engine(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                return _HangingBeginEngine(5)
            return real_create_async_engine(*args, **kwargs)

        monkeypatch.setattr(s, "create_async_engine", _engine)
        try:
            asyncio.run(s.init_db())  # must NOT raise in DEBUG mode
            assert calls["n"] == 2
            assert s._backend == "sqlite"
        finally:
            _restore_engine_globals(s)


# --------------------------------------------------------------------------
# passlib / bcrypt compatibility
# --------------------------------------------------------------------------

class TestBcryptCompat:
    def test_hash_and_verify_roundtrip(self):
        from app.core.auth import hash_password, verify_password
        password = f"str0ng-pass-{uuid.uuid4().hex}"
        hashed = hash_password(password)
        assert hashed.startswith("$2b$")
        assert hashed != password  # never stored in plaintext
        assert verify_password(password, hashed) is True
        assert verify_password("wrong-password", hashed) is False

    def test_no_bcrypt_version_trapped_error(self, caplog):
        """passlib 1.7.4 + bcrypt 4.0.x must not log
        '(trapped) error reading bcrypt version'."""
        from app.core.auth import hash_password
        with caplog.at_level(logging.WARNING, logger="passlib.handlers.bcrypt"):
            hash_password("another-demo-pass")
        assert "error reading bcrypt version" not in caplog.text


# --------------------------------------------------------------------------
# Auth flow: demo credentials, register/login/logout, isolation
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _register(client, name: str, email: str, password: str):
    return client.post(
        "/api/v1/auth/register",
        json={"name": name, "email": email, "password": password, "confirm_password": password},
    )


class TestAuthFlow:
    def test_demo_credentials_login(self, client):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@fraudlens.io", "password": "fraudlens"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["token"]
        assert body["user"]["email"] == "admin@fraudlens.io"
        assert body["user"]["role"] == "admin"

    def test_demo_credentials_wrong_password_rejected(self, client):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@fraudlens.io", "password": "not-the-password"},
        )
        assert resp.status_code == 401

    def test_register_rejects_password_over_72_bytes(self, client):
        email = f"longpass-{uuid.uuid4().hex[:8]}@example.com"
        resp = _register(client, "Long Password", email, "a" * 73)
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert any("72 bytes" in str(d) for d in detail)

    def test_register_accepts_exactly_72_bytes(self, client):
        email = f"max72-{uuid.uuid4().hex[:8]}@example.com"
        password = "a" * 72
        resp = _register(client, "Max 72", email, password)
        assert resp.status_code == 200, resp.text
        # And the user can log in with it.
        login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert login.status_code == 200

    def test_register_duplicate_email_rejected(self, client):
        email = f"dup-{uuid.uuid4().hex[:8]}@example.com"
        assert _register(client, "First", email, "password123").status_code == 200
        resp = _register(client, "Second", email, "password123")
        assert resp.status_code == 409

    def test_register_login_logout_flow(self, client):
        email = f"flow-{uuid.uuid4().hex[:8]}@example.com"
        register = _register(client, "Flow User", email, "password123")
        assert register.status_code == 200
        token = register.json()["token"]

        me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["user"]["email"] == email

        logout = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert logout.status_code == 200

        # Token must be invalidated after logout.
        me_after = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_after.status_code == 401

    def test_user_isolation(self, client):
        email_a = f"iso-a-{uuid.uuid4().hex[:8]}@example.com"
        email_b = f"iso-b-{uuid.uuid4().hex[:8]}@example.com"

        register_a = _register(client, "User A", email_a, "passwordA1")
        assert register_a.status_code == 200
        login_a = client.post("/api/v1/auth/login", json={"email": email_a, "password": "passwordA1"})
        assert login_a.status_code == 200
        token_a = login_a.json()["token"]

        register_b = _register(client, "User B", email_b, "passwordB1")
        assert register_b.status_code == 200
        login_b = client.post("/api/v1/auth/login", json={"email": email_b, "password": "passwordB1"})
        assert login_b.status_code == 200
        token_b = login_b.json()["token"]

        me_a = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_a}"})
        me_b = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_b}"})
        assert me_a.json()["user"]["email"] == email_a
        assert me_b.json()["user"]["email"] == email_b

        # Activity log is owner-scoped: B must only ever see B's own events
        # (a REGISTER and a LOGIN), never A's.
        activity_b = client.get(
            "/api/v1/auth/activity", headers={"Authorization": f"Bearer {token_b}"}
        )
        assert activity_b.status_code == 200
        body = activity_b.json()
        assert body["total"] == 2
        assert all(email_a not in str(a.get("description", "")) for a in body["activities"])

        # A sees only A's events too.
        activity_a = client.get(
            "/api/v1/auth/activity", headers={"Authorization": f"Bearer {token_a}"}
        )
        assert activity_a.json()["total"] == 2

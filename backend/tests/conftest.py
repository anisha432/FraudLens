"""Shared pytest configuration.

Forces a throwaway SQLite database and ``DEBUG=true`` for every test run so the
real local development database (``backend/fraud_detection.db``) is never
touched and production fail-fast behavior can be tested in isolation.

This module is imported by pytest before any test module, so the environment
below is in place before ``app.core.config.get_settings()`` is first called.
"""
import os
import tempfile

_TEST_DIR = tempfile.mkdtemp(prefix="fraudlens_tests_")
_DB_FILE = os.path.join(_TEST_DIR, "test.db").replace("\\", "/")

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_DB_FILE}"
os.environ["DATABASE_URL_SYNC"] = f"sqlite:///{_DB_FILE}"
os.environ["DEBUG"] = "true"

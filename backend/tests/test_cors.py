"""CORS configuration regression tests.

The production frontend (https://fraudlens-frontend-1irz.onrender.com) must be
allowed by the backend's CORSMiddleware even when the ``CORS_ORIGINS`` env var
is unset or misconfigured on the deployment — otherwise the browser blocks
requests such as ``POST /api/v1/auth/register`` at the preflight stage with
\"No 'Access-Control-Allow-Origin' header is present\".

Rules under test:
* DEBUG mode keeps ``[\"*\"]`` (local development convenience).
* Production never uses ``[\"*\"]`` (the app uses authentication).
* Production always includes the FraudLens frontend origin, merged with (never
  replaced by) whatever origins are configured via ``CORS_ORIGINS``.
"""
from __future__ import annotations

from app.main import PROD_FRONTEND_ORIGINS, resolve_cors_origins

LOCALHOST_ORIGINS = ["http://localhost:3000", "http://localhost:5173"]


class TestResolveCorsOrigins:
    def test_debug_allows_all_origins(self):
        assert resolve_cors_origins(debug=True, configured_origins=LOCALHOST_ORIGINS) == ["*"]

    def test_production_never_uses_wildcard(self):
        origins = resolve_cors_origins(debug=False, configured_origins=LOCALHOST_ORIGINS)
        assert "*" not in origins

    def test_production_allows_prod_frontend_with_default_localhost_config(self):
        # Regression: a backend started with DEBUG=false and no/only-localhost
        # CORS_ORIGINS must still answer preflights from the deployed frontend.
        origins = resolve_cors_origins(debug=False, configured_origins=LOCALHOST_ORIGINS)
        assert origins == [*LOCALHOST_ORIGINS, "https://fraudlens-frontend-1irz.onrender.com"]
        assert "https://fraudlens-frontend-1irz.onrender.com" in origins

    def test_production_allows_prod_frontend_when_env_unset(self):
        # CORS_ORIGINS unset on the deployment -> pydantic default is the
        # localhost list; the frontend origin must still be present.
        origins = resolve_cors_origins(debug=False, configured_origins=LOCALHOST_ORIGINS)
        assert "https://fraudlens-frontend-1irz.onrender.com" in origins

    def test_production_allows_prod_frontend_when_env_empty(self):
        origins = resolve_cors_origins(debug=False, configured_origins=[])
        assert origins == ["https://fraudlens-frontend-1irz.onrender.com"]

    def test_prod_frontend_origin_is_not_duplicated_when_already_configured(self):
        configured = ["https://fraudlens-frontend-1irz.onrender.com", "https://app.example.com"]
        origins = resolve_cors_origins(debug=False, configured_origins=configured)
        assert origins == configured

    def test_configured_origins_come_first_then_prod_frontend(self):
        origins = resolve_cors_origins(debug=False, configured_origins=["https://staging.example.com"])
        assert origins == ["https://staging.example.com", "https://fraudlens-frontend-1irz.onrender.com"]

    def test_prod_frontend_origin_is_an_https_url(self):
        assert len(PROD_FRONTEND_ORIGINS) == 1
        assert PROD_FRONTEND_ORIGINS[0].startswith("https://")

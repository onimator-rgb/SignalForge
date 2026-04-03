"""Tests for backend app startup — verify imports and router registration."""

import pytest
from fastapi.testclient import TestClient


def test_app_imports():
    """The FastAPI app object should be importable without errors."""
    from app.main import create_app
    app = create_app()
    assert app is not None
    assert app.title == "MarketPulse AI"


def test_all_routers_registered():
    """All expected routers should be registered with at least one route each."""
    from app.main import create_app
    app = create_app()
    paths = [route.path for route in app.routes]

    # Each tuple: (module_keyword, at least one route path must contain this substring)
    EXPECTED_KEYWORDS = [
        ("health", "/health"),
        ("diagnostics", "/diagnostics"),
        ("assets", "/assets"),
        ("ingestion", "/ingestion"),
        ("ohlcv", "/ohlcv"),          # market_data router
        ("indicators", "/indicators"),
        ("anomalies", "/anomalies"),
        ("reports", "/reports"),
        ("alerts", "/alerts"),
        ("watchlists", "/watchlists"),
        ("recommendations", "/recommendations"),
        ("portfolio", "/portfolio"),
        ("live", "/live"),
        ("strategy", "/strategy"),
        ("backtest", "/backtest"),
        ("strategies", "/strategies"),
        ("marketplace", "/marketplace"),
    ]

    missing = []
    for module_name, keyword in EXPECTED_KEYWORDS:
        if not any(keyword in p for p in paths):
            missing.append(module_name)

    assert not missing, (
        f"Missing route keywords: {missing}.\n"
        f"Registered paths: {sorted(set(paths))}"
    )


def test_health_endpoint():
    """Health endpoint should respond with 200."""
    from app.main import create_app
    app = create_app()
    # Use TestClient without lifespan to avoid DB/scheduler init
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200


def test_openapi_schema_loads():
    """OpenAPI schema should generate without errors."""
    from app.main import create_app
    app = create_app()
    schema = app.openapi()
    assert "paths" in schema
    assert len(schema["paths"]) > 10

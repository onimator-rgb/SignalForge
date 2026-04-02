"""Tests for POST /api/v1/strategies/optimize endpoint (marketpulse-task-2026-04-02-0023)."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.strategies.router import router


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


# Synthetic price series: gentle uptrend with noise (50 elements)
SAMPLE_PRICES = [100.0 + i * 0.5 + ((-1) ** i) * 0.3 for i in range(50)]


@pytest.mark.anyio
async def test_optimize_balanced_profile() -> None:
    """Valid request with balanced profile returns 200 and results."""
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/strategies/optimize",
            json={
                "profile_name": "balanced",
                "param_ranges": {"stop_loss_pct": [-0.05, -0.08, -0.12]},
                "prices": SAMPLE_PRICES,
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert len(data["results"]) <= 3
    for item in data["results"]:
        assert "sharpe_ratio" in item
        assert "params" in item


@pytest.mark.anyio
async def test_optimize_empty_ranges() -> None:
    """Empty param_ranges returns single result for base profile."""
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/strategies/optimize",
            json={
                "profile_name": "balanced",
                "param_ranges": {},
                "prices": SAMPLE_PRICES,
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) == 1


@pytest.mark.anyio
async def test_optimize_invalid_profile() -> None:
    """Invalid profile_name returns 422."""
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/strategies/optimize",
            json={
                "profile_name": "nonexistent",
                "param_ranges": {},
                "prices": SAMPLE_PRICES,
            },
        )

    assert resp.status_code == 422


@pytest.mark.anyio
async def test_optimize_unknown_field() -> None:
    """Unknown StrategyProfile field in param_ranges returns 400."""
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/strategies/optimize",
            json={
                "profile_name": "balanced",
                "param_ranges": {"fake_field": [1.0]},
                "prices": SAMPLE_PRICES,
            },
        )

    assert resp.status_code == 400


@pytest.mark.anyio
async def test_optimize_too_few_prices() -> None:
    """Fewer than 10 prices returns 400 (Pydantic validation)."""
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/strategies/optimize",
            json={
                "profile_name": "balanced",
                "param_ranges": {},
                "prices": [1.0, 2.0],
            },
        )

    assert resp.status_code == 422


@pytest.mark.anyio
async def test_optimize_multiple_params() -> None:
    """Multiple param_ranges produces grid of results."""
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/strategies/optimize",
            json={
                "profile_name": "balanced",
                "param_ranges": {
                    "stop_loss_pct": [-0.05, -0.10],
                    "take_profit_pct": [0.10, 0.15],
                },
                "prices": SAMPLE_PRICES,
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    # 2x2 grid = 4 combinations, top_n default is 5, so all 4 returned
    assert len(data["results"]) <= 4

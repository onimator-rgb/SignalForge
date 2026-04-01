"""Tests for POST /api/v1/backtest/run endpoint (marketpulse-task-2026-04-01-0001)."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.backtest.router import router
from app.database import get_db


def _build_app(mock_db: AsyncMock) -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    async def _override() -> AsyncMock:  # type: ignore[misc]
        yield mock_db

    app.dependency_overrides[get_db] = _override
    return app


def _make_price_rows(prices: list[float]) -> list[MagicMock]:
    """Create mock rows with a .close attribute."""
    rows = []
    for p in prices:
        row = MagicMock()
        row.close = p
        rows.append(row)
    return rows


SAMPLE_PRICES = [100.0, 102.0, 101.0, 105.0, 103.0, 108.0, 107.0, 110.0, 109.0, 112.0]


@pytest.mark.asyncio
async def test_successful_backtest() -> None:
    """Valid request returns 200 with BacktestResponse fields."""
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.all.return_value = _make_price_rows(SAMPLE_PRICES)
    db.execute = AsyncMock(return_value=result_mock)

    app = _build_app(db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/backtest/run",
            json={"asset_id": str(uuid.uuid4()), "profile_name": "balanced"},
        )

    assert resp.status_code == 200
    data = resp.json()
    # Check all required metric fields exist
    for field in [
        "total_return",
        "total_return_pct",
        "max_drawdown_pct",
        "sharpe_ratio",
        "win_rate",
        "profit_factor",
        "total_trades",
        "avg_trade_pnl_pct",
        "best_trade_pnl_pct",
        "worst_trade_pnl_pct",
        "trades",
    ]:
        assert field in data, f"Missing field: {field}"
    assert isinstance(data["trades"], list)


@pytest.mark.asyncio
async def test_trades_have_required_fields() -> None:
    """Each trade in response has all required fields."""
    db = AsyncMock()
    result_mock = MagicMock()
    # Use prices that will produce at least one trade (large upswing)
    prices = [100.0, 90.0, 85.0, 80.0, 95.0, 110.0, 120.0, 130.0, 140.0, 150.0]
    result_mock.all.return_value = _make_price_rows(prices)
    db.execute = AsyncMock(return_value=result_mock)

    app = _build_app(db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/backtest/run",
            json={"asset_id": str(uuid.uuid4()), "profile_name": "aggressive"},
        )

    assert resp.status_code == 200
    data = resp.json()
    for trade in data["trades"]:
        for field in [
            "entry_index",
            "exit_index",
            "entry_price",
            "exit_price",
            "pnl",
            "pnl_pct",
            "exit_reason",
        ]:
            assert field in trade, f"Missing trade field: {field}"


@pytest.mark.asyncio
async def test_not_enough_price_data_returns_404() -> None:
    """Asset with fewer than 2 price bars returns 404."""
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.all.return_value = _make_price_rows([100.0])  # Only 1 bar
    db.execute = AsyncMock(return_value=result_mock)

    app = _build_app(db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/backtest/run",
            json={"asset_id": str(uuid.uuid4())},
        )

    assert resp.status_code == 404
    assert "Not enough price data" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_no_price_data_returns_404() -> None:
    """Asset with zero price bars returns 404."""
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.all.return_value = []
    db.execute = AsyncMock(return_value=result_mock)

    app = _build_app(db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/backtest/run",
            json={"asset_id": str(uuid.uuid4())},
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_invalid_profile_returns_400() -> None:
    """Unknown profile_name returns 400."""
    db = AsyncMock()

    app = _build_app(db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/backtest/run",
            json={"asset_id": str(uuid.uuid4()), "profile_name": "nonexistent"},
        )

    assert resp.status_code == 400
    assert "Unknown profile" in resp.json()["detail"]

"""Tests for AI Assistant API endpoints (marketpulse-task-2026-04-02-0027)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.ai_assistant.router import router
from app.database import get_db


def _build_app(mock_db: AsyncMock) -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    async def _override() -> AsyncMock:  # type: ignore[misc]
        yield mock_db

    app.dependency_overrides[get_db] = _override
    return app


def _mock_scalars_empty(mock_db: AsyncMock) -> None:
    """Configure mock DB to return empty results for all queries."""
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    result_mock.all.return_value = []
    mock_db.execute = AsyncMock(return_value=result_mock)


def _mock_with_portfolio(mock_db: AsyncMock) -> None:
    """Configure mock DB with an active portfolio but no positions/transactions."""
    portfolio = MagicMock()
    portfolio.id = "test-portfolio-id"
    portfolio.current_cash = 1000.0
    portfolio.initial_capital = 1000.0
    portfolio.is_active = True

    # First call returns portfolio, subsequent calls return empty lists
    call_count = 0

    async def _execute(stmt: object) -> MagicMock:
        nonlocal call_count
        result = MagicMock()
        if call_count == 0:
            # Portfolio query
            result.scalar_one_or_none.return_value = portfolio
        else:
            # Positions and transactions queries
            result.all.return_value = []
        call_count += 1
        return result

    mock_db.execute = _execute


@pytest.mark.asyncio
async def test_portfolio_report_no_portfolio() -> None:
    """No active portfolio returns 200 with a minimal report."""
    db = AsyncMock()
    _mock_scalars_empty(db)

    app = _build_app(db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/ai/portfolio-report")

    assert resp.status_code == 200
    data = resp.json()
    assert "report" in data
    assert isinstance(data["report"], str)
    assert len(data["report"]) > 0


@pytest.mark.asyncio
async def test_portfolio_report_with_empty_portfolio() -> None:
    """Active portfolio with no positions returns 200 with report."""
    db = AsyncMock()
    _mock_with_portfolio(db)

    app = _build_app(db)

    with patch("app.strategy.regime.calculate_regime", new_callable=AsyncMock) as mock_regime:
        mock_regime.return_value = {"regime": "neutral", "score": 0}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/ai/portfolio-report")

    assert resp.status_code == 200
    data = resp.json()
    assert "report" in data
    assert "PORTFOLIO SUMMARY" in data["report"]


@pytest.mark.asyncio
async def test_strategy_suggestions_returns_200() -> None:
    """Strategy suggestions endpoint returns 200 with suggestions key."""
    db = AsyncMock()

    app = _build_app(db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/ai/strategy-suggestions/test-strategy-1")

    assert resp.status_code == 200
    data = resp.json()
    assert "suggestions" in data
    assert isinstance(data["suggestions"], list)
    assert data["strategy_id"] == "test-strategy-1"


@pytest.mark.asyncio
async def test_strategy_suggestions_different_ids() -> None:
    """Strategy suggestions echoes back the correct strategy_id."""
    db = AsyncMock()

    app = _build_app(db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/ai/strategy-suggestions/my-custom-id")

    assert resp.status_code == 200
    assert resp.json()["strategy_id"] == "my-custom-id"

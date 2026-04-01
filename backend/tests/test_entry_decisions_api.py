"""Tests for enriched entry-decisions API endpoint (marketpulse-task-2026-04-01-0033)."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.portfolio.router import router


def _make_decision(
    *,
    status: str = "allowed",
    stage: str = "ranking",
    context_data: dict | None = None,
    reason_codes: list[str] | None = None,
    reason_text: str | None = None,
    regime: str | None = "bullish",
    profile: str | None = "balanced",
) -> MagicMock:
    """Build a mock EntryDecision + joined Asset row."""
    row = MagicMock()
    decision = MagicMock()
    decision.id = uuid.uuid4()
    decision.status = status
    decision.stage = stage
    decision.reason_codes = reason_codes
    decision.reason_text = reason_text
    decision.context_data = context_data
    decision.regime = regime
    decision.profile = profile
    decision.created_at = datetime(2026, 3, 30, 12, 0, tzinfo=timezone.utc)

    row.EntryDecision = decision
    row.symbol = "BTC"
    row.asset_class = "crypto"
    return row


def _build_app(mock_db: AsyncMock) -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    async def _override() -> AsyncMock:  # type: ignore[misc]
        yield mock_db

    app.dependency_overrides[get_db] = _override
    return app


@pytest.mark.asyncio
async def test_entry_decisions_returns_context_data() -> None:
    """Endpoint returns context_data, ranking_score, allocation_multiplier."""
    ctx = {"ranking_score": 78.5, "allocation_multiplier": 1.2, "confirmations": {"rsi": True}}
    row = _make_decision(context_data=ctx)

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.all.return_value = [row]
    db.execute = AsyncMock(return_value=result_mock)

    app = _build_app(db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/portfolio/entry-decisions")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1

    d = data[0]
    # Existing fields still present
    assert d["symbol"] == "BTC"
    assert d["asset_class"] == "crypto"
    assert d["status"] == "allowed"
    assert d["stage"] == "ranking"
    assert d["regime"] == "bullish"
    assert d["profile"] == "balanced"
    assert "created_at" in d

    # New enriched fields
    assert d["context_data"] == ctx
    assert d["ranking_score"] == 78.5
    assert d["allocation_multiplier"] == 1.2


@pytest.mark.asyncio
async def test_entry_decisions_null_context_data() -> None:
    """When context_data is None, ranking_score and allocation_multiplier are null."""
    row = _make_decision(context_data=None)

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.all.return_value = [row]
    db.execute = AsyncMock(return_value=result_mock)

    app = _build_app(db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/portfolio/entry-decisions")

    assert resp.status_code == 200
    d = resp.json()[0]
    assert d["context_data"] == {}
    assert d["ranking_score"] is None
    assert d["allocation_multiplier"] is None


@pytest.mark.asyncio
async def test_entry_decisions_blocked_with_reasons() -> None:
    """Blocked decision with reason_codes is returned correctly."""
    row = _make_decision(
        status="blocked",
        stage="protections",
        reason_codes=["daily_loss_limit", "max_positions"],
        reason_text="Daily loss limit exceeded; max positions reached",
        context_data={"ranking_score": 45.0},
        regime="bearish",
        profile="conservative",
    )

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.all.return_value = [row]
    db.execute = AsyncMock(return_value=result_mock)

    app = _build_app(db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/portfolio/entry-decisions?status=blocked")

    assert resp.status_code == 200
    d = resp.json()[0]
    assert d["status"] == "blocked"
    assert d["stage"] == "protections"
    assert d["reason_codes"] == ["daily_loss_limit", "max_positions"]
    assert d["reason_text"] == "Daily loss limit exceeded; max positions reached"
    assert d["ranking_score"] == 45.0
    assert d["allocation_multiplier"] is None
    assert d["regime"] == "bearish"
    assert d["profile"] == "conservative"

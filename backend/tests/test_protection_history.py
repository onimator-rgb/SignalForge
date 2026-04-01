"""Tests for GET /api/v1/portfolio/protection-history (marketpulse-task-2026-04-01-0007)."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.portfolio.router import router


def _make_protection(
    *,
    protection_type: str = "stoploss_guard",
    status: str = "active",
    reason: str = "Daily loss limit hit",
    asset_id: uuid.UUID | None = None,
    asset_class: str | None = None,
    triggered_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> MagicMock:
    row = MagicMock()
    row.id = uuid.uuid4()
    row.protection_type = protection_type
    row.status = status
    row.asset_id = asset_id
    row.asset_class = asset_class
    row.reason = reason
    row.triggered_at = triggered_at or datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc)
    row.expires_at = expires_at
    row.created_at = datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc)
    return row


def _build_app(mock_db: AsyncMock) -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    async def _override() -> AsyncMock:  # type: ignore[misc]
        yield mock_db

    app.dependency_overrides[get_db] = _override
    return app


@pytest.mark.asyncio
async def test_protection_history_returns_200_with_list() -> None:
    """GET /api/v1/portfolio/protection-history returns 200 with a JSON list."""
    rows = [_make_protection(), _make_protection(protection_type="asset_cooldown", status="expired")]

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = rows
    db.execute = AsyncMock(return_value=result_mock)

    app = _build_app(db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/portfolio/protection-history")

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2

    # Check required fields
    for item in data:
        assert "id" in item
        assert "protection_type" in item
        assert "status" in item
        assert "reason" in item
        assert "created_at" in item

    assert data[0]["protection_type"] == "stoploss_guard"
    assert data[1]["protection_type"] == "asset_cooldown"
    assert data[1]["status"] == "expired"


@pytest.mark.asyncio
async def test_protection_history_limit_param() -> None:
    """The limit query parameter caps the number of results."""
    rows = [_make_protection()]

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = rows
    db.execute = AsyncMock(return_value=result_mock)

    app = _build_app(db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/portfolio/protection-history?limit=5")

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1


@pytest.mark.asyncio
async def test_protection_history_empty() -> None:
    """Returns empty list when no protection events exist."""
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=result_mock)

    app = _build_app(db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/portfolio/protection-history")

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_protection_history_fields_serialization() -> None:
    """Fields are correctly serialized: asset_id as string, datetimes as ISO."""
    aid = uuid.uuid4()
    row = _make_protection(
        asset_id=aid,
        asset_class="crypto",
        expires_at=datetime(2026, 4, 2, 10, 0, tzinfo=timezone.utc),
    )

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [row]
    db.execute = AsyncMock(return_value=result_mock)

    app = _build_app(db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/portfolio/protection-history")

    assert resp.status_code == 200
    item = resp.json()[0]
    assert item["asset_id"] == str(aid)
    assert item["asset_class"] == "crypto"
    assert "2026-04-01" in item["triggered_at"]
    assert "2026-04-02" in item["expires_at"]
    assert "2026-04-01" in item["created_at"]

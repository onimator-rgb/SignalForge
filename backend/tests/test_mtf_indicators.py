"""Tests for multi-timeframe indicators (marketpulse-task-2026-04-01-0013)."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.indicators.schemas import (
    IndicatorSnapshot,
    MultiTimeframeIndicators,
)
from app.indicators.service import get_multi_timeframe_indicators

FAKE_ASSET_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
FAKE_SYMBOL = "BTC/USD"


def _make_snapshot(interval: str) -> IndicatorSnapshot:
    return IndicatorSnapshot(
        asset_id=FAKE_ASSET_ID,
        asset_symbol=FAKE_SYMBOL,
        interval=interval,
        bar_time=datetime.now(tz=timezone.utc),
        close=100.0,
        bars_available=60,
    )


@pytest.mark.asyncio
async def test_get_multi_timeframe_default_intervals() -> None:
    """With intervals=None, should call get_indicators 4 times for default intervals."""
    mock_db = AsyncMock()

    async def fake_get_indicators(
        db: object, asset_id: object, asset_symbol: object, interval: str = "1h", lookback: int = 60
    ) -> IndicatorSnapshot:
        return _make_snapshot(interval)

    with patch("app.indicators.service.get_indicators", side_effect=fake_get_indicators) as mock_gi:
        result = await get_multi_timeframe_indicators(mock_db, FAKE_ASSET_ID, FAKE_SYMBOL, intervals=None)

    assert mock_gi.call_count == 4
    assert set(result.keys()) == {"5m", "1h", "4h", "1d"}
    for key, snap in result.items():
        assert snap is not None
        assert snap.interval == key


@pytest.mark.asyncio
async def test_get_multi_timeframe_custom_intervals() -> None:
    """With custom intervals, only those intervals should be fetched."""
    mock_db = AsyncMock()

    async def fake_get_indicators(
        db: object, asset_id: object, asset_symbol: object, interval: str = "1h", lookback: int = 60
    ) -> IndicatorSnapshot:
        return _make_snapshot(interval)

    with patch("app.indicators.service.get_indicators", side_effect=fake_get_indicators) as mock_gi:
        result = await get_multi_timeframe_indicators(
            mock_db, FAKE_ASSET_ID, FAKE_SYMBOL, intervals=["1h", "1d"]
        )

    assert mock_gi.call_count == 2
    assert set(result.keys()) == {"1h", "1d"}


@pytest.mark.asyncio
async def test_get_multi_timeframe_handles_none_results() -> None:
    """If get_indicators returns None for an interval, that key maps to None."""
    mock_db = AsyncMock()

    async def fake_get_indicators(
        db: object, asset_id: object, asset_symbol: object, interval: str = "1h", lookback: int = 60
    ) -> IndicatorSnapshot | None:
        if interval == "4h":
            return None
        return _make_snapshot(interval)

    with patch("app.indicators.service.get_indicators", side_effect=fake_get_indicators):
        result = await get_multi_timeframe_indicators(mock_db, FAKE_ASSET_ID, FAKE_SYMBOL)

    assert result["4h"] is None
    assert result["5m"] is not None
    assert result["1h"] is not None
    assert result["1d"] is not None


@pytest.mark.asyncio
async def test_get_multi_timeframe_concurrent_execution() -> None:
    """Verify asyncio.gather is used for concurrent execution."""
    mock_db = AsyncMock()

    async def fake_get_indicators(
        db: object, asset_id: object, asset_symbol: object, interval: str = "1h", lookback: int = 60
    ) -> IndicatorSnapshot:
        return _make_snapshot(interval)

    with patch("app.indicators.service.get_indicators", side_effect=fake_get_indicators):
        with patch("app.indicators.service.asyncio.gather", wraps=__import__("asyncio").gather) as mock_gather:
            result = await get_multi_timeframe_indicators(mock_db, FAKE_ASSET_ID, FAKE_SYMBOL)

    mock_gather.assert_called_once()
    assert len(result) == 4


def test_mtf_schema_serialization() -> None:
    """MultiTimeframeIndicators should serialize correctly with model_dump()."""
    now = datetime.now(tz=timezone.utc)
    snap = _make_snapshot("1h")
    mtf = MultiTimeframeIndicators(
        asset_id=FAKE_ASSET_ID,
        timeframes={"1h": snap, "4h": None},
        computed_at=now,
    )
    data = mtf.model_dump()
    assert data["asset_id"] == FAKE_ASSET_ID
    assert "1h" in data["timeframes"]
    assert data["timeframes"]["4h"] is None
    assert data["timeframes"]["1h"]["interval"] == "1h"
    assert data["computed_at"] == now

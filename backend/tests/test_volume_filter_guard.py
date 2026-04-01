"""Tests for minimum volume filter protection guard.

Task: marketpulse-task-2026-04-01-0009
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.anomalies.models  # noqa: F401 — ensure all mappers are registered
from app.portfolio.protections import (
    MIN_VOLUME_USD,
    _check_volume_filter,
)


NOW = datetime(2026, 4, 1, 14, 30, 0, tzinfo=timezone.utc)
ASSET_ID = uuid.uuid4()


def _make_bar(close: float, volume: float) -> MagicMock:
    """Create a mock PriceBar row with close and volume attributes."""
    bar = MagicMock()
    bar.close = close
    bar.volume = volume
    return bar


def _make_db(rows: list[MagicMock]) -> AsyncMock:
    """Build AsyncSession mock whose execute().all() returns *rows*."""
    db = AsyncMock()
    result = MagicMock()
    result.all.return_value = rows
    db.execute.return_value = result
    return db


@pytest.mark.asyncio
async def test_volume_above_threshold_allows_entry() -> None:
    """Sufficient volume should allow entry."""
    # crypto threshold = $100k, produce 24 bars with $5k each = $120k
    bars = [_make_bar(close=100.0, volume=50.0) for _ in range(24)]
    db = _make_db(bars)

    blocked, reason = await _check_volume_filter(db, ASSET_ID, "crypto", NOW)

    assert not blocked
    assert reason is None


@pytest.mark.asyncio
async def test_volume_below_threshold_blocks_entry() -> None:
    """Low volume should block entry with descriptive reason."""
    # crypto threshold = $100k, produce 10 bars with $1k each = $10k
    bars = [_make_bar(close=100.0, volume=10.0) for _ in range(10)]
    db = _make_db(bars)

    blocked, reason = await _check_volume_filter(db, ASSET_ID, "crypto", NOW)

    assert blocked
    assert reason is not None
    assert "$10,000" in reason
    assert "$100,000" in reason
    assert "crypto" in reason


@pytest.mark.asyncio
async def test_no_bars_blocks_entry() -> None:
    """No price bars should block entry due to insufficient data."""
    db = _make_db([])

    blocked, reason = await _check_volume_filter(db, ASSET_ID, "crypto", NOW)

    assert blocked
    assert reason is not None
    assert "insufficient data" in reason.lower()


@pytest.mark.asyncio
async def test_asset_class_specific_thresholds() -> None:
    """Stock threshold ($1M) should differ from crypto threshold ($100k)."""
    # 24 bars × $200 × 250 qty = $1.2M → passes stock threshold
    bars_high = [_make_bar(close=200.0, volume=250.0) for _ in range(24)]

    db = _make_db(bars_high)
    blocked, _ = await _check_volume_filter(db, ASSET_ID, "stock", NOW)
    assert not blocked

    # 24 bars × $200 × 100 qty = $480k → below $1M stock threshold
    bars_low = [_make_bar(close=200.0, volume=100.0) for _ in range(24)]
    db = _make_db(bars_low)
    blocked, reason = await _check_volume_filter(db, ASSET_ID, "stock", NOW)
    assert blocked
    assert reason is not None
    assert f"${MIN_VOLUME_USD['stock']:,.0f}" in reason


@pytest.mark.asyncio
async def test_default_threshold_for_unknown_class() -> None:
    """Unknown asset class should fall back to 'default' threshold ($50k)."""
    # 24 bars × $50 × 50 qty = $60k → above $50k default
    bars = [_make_bar(close=50.0, volume=50.0) for _ in range(24)]
    db = _make_db(bars)

    blocked, reason = await _check_volume_filter(db, ASSET_ID, "forex", NOW)

    assert not blocked
    assert reason is None

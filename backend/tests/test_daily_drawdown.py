"""Tests for daily drawdown circuit breaker protection guard.

Task: marketpulse-task-2026-04-01-0029
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.anomalies.models  # noqa: F401 — ensure all mappers are registered
from app.portfolio.protections import _daily_drawdown_guard
from app.portfolio.rules import DAILY_DRAWDOWN_LIMIT_PCT


# ── Helpers ──────────────────────────────────────────


NOW = datetime(2026, 4, 1, 14, 30, 0, tzinfo=timezone.utc)
DAY_START = NOW.replace(hour=0, minute=0, second=0, microsecond=0)
DAY_END = DAY_START + timedelta(days=1)
PORTFOLIO_ID = uuid.uuid4()


def _make_scalar_result(value: Any) -> MagicMock:
    """Build a mock DB result whose .scalar_one() returns *value*."""
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


def _make_scalars_result_first(value: Any) -> MagicMock:
    """Build a mock DB result whose .scalars().first() returns *value*."""
    result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.first.return_value = value
    result.scalars.return_value = scalars_mock
    return result


def _make_snapshot(day_open_equity: float) -> MagicMock:
    """Create a mock ProtectionEvent snapshot with context_data."""
    snap = MagicMock()
    snap.context_data = {"day_open_equity": day_open_equity, "date": "2026-04-01"}
    return snap


def _build_db_no_block(
    day_open_equity: float,
    current_cash: float,
    positions_value: float,
    *,
    snapshot_exists: bool = True,
) -> AsyncMock:
    """Build AsyncSession mock for a scenario where no block is triggered.

    Execute calls in order:
    1. active block count → 0
    2. portfolio current_cash
    3. sum of open position values
    4. snapshot query → existing or None
    (if snapshot_exists=False: flush is called after db.add)
    """
    db = AsyncMock()
    db.add = MagicMock()  # add() is synchronous on AsyncSession
    results: list[Any] = [
        # 1. active daily_drawdown count
        _make_scalar_result(0),
        # 2. portfolio current_cash
        _make_scalar_result(current_cash),
        # 3. sum open positions
        _make_scalar_result(positions_value),
    ]

    if snapshot_exists:
        # 4. snapshot query returns existing snapshot
        results.append(_make_scalars_result_first(_make_snapshot(day_open_equity)))
    else:
        # 4. snapshot query returns None (will create new)
        results.append(_make_scalars_result_first(None))

    db.execute = AsyncMock(side_effect=results)
    return db


def _build_db_already_blocked() -> AsyncMock:
    """Build AsyncSession mock for scenario where daily_drawdown is already active."""
    db = AsyncMock()
    db.add = MagicMock()
    db.execute = AsyncMock(side_effect=[
        # 1. active daily_drawdown count → 1
        _make_scalar_result(1),
    ])
    return db


# ── Tests ────────────────────────────────────────────


class TestNoBlockWhenEquityAboveThreshold:
    """4% drop (below 5% threshold) → entry allowed."""

    @pytest.mark.asyncio
    async def test_allows_entry(self) -> None:
        # day_open=1000, current=960 → 4% drop
        db = _build_db_no_block(
            day_open_equity=1000.0,
            current_cash=460.0,
            positions_value=500.0,
            snapshot_exists=True,
        )

        allowed, ptype, reason = await _daily_drawdown_guard(db, PORTFOLIO_ID, NOW)

        assert allowed is True
        assert ptype is None
        assert reason is None


class TestBlockWhenEquityBelowThreshold:
    """6% drop (above 5% threshold) → entry blocked."""

    @pytest.mark.asyncio
    async def test_blocks_entry(self) -> None:
        # day_open=1000, current=940 → 6% drop
        db = _build_db_no_block(
            day_open_equity=1000.0,
            current_cash=440.0,
            positions_value=500.0,
            snapshot_exists=True,
        )

        allowed, ptype, reason = await _daily_drawdown_guard(db, PORTFOLIO_ID, NOW)

        assert allowed is False
        assert ptype == "daily_drawdown"
        assert reason is not None
        assert "6.0%" in reason
        assert "$1000.00" in reason
        assert "$940.00" in reason
        # Verify a ProtectionEvent was added
        db.add.assert_called()
        db.flush.assert_awaited()


class TestBlockAtExactThreshold:
    """Exactly 5% drop → entry blocked (>= comparison)."""

    @pytest.mark.asyncio
    async def test_exact_threshold_blocks(self) -> None:
        # day_open=1000, current=950 → exactly 5% drop
        db = _build_db_no_block(
            day_open_equity=1000.0,
            current_cash=450.0,
            positions_value=500.0,
            snapshot_exists=True,
        )

        allowed, ptype, reason = await _daily_drawdown_guard(db, PORTFOLIO_ID, NOW)

        assert allowed is False
        assert ptype == "daily_drawdown"
        assert reason is not None
        assert "5.0%" in reason


class TestCreatesSnapshotOnFirstCall:
    """When no snapshot exists for today, one is created."""

    @pytest.mark.asyncio
    async def test_creates_snapshot(self) -> None:
        # No snapshot exists, current equity = 1000 (no drop)
        db = _build_db_no_block(
            day_open_equity=1000.0,  # won't be used since snapshot_exists=False
            current_cash=500.0,
            positions_value=500.0,
            snapshot_exists=False,
        )

        allowed, ptype, reason = await _daily_drawdown_guard(db, PORTFOLIO_ID, NOW)

        assert allowed is True
        assert ptype is None
        # Verify snapshot was created via db.add
        db.add.assert_called_once()
        added_event = db.add.call_args[0][0]
        assert added_event.protection_type == "daily_equity_snapshot"
        assert added_event.status == "expired"
        assert added_event.context_data["day_open_equity"] == 1000.0
        assert added_event.context_data["date"] == "2026-04-01"
        db.flush.assert_awaited()


class TestReusesExistingSnapshot:
    """When snapshot already exists for today, uses stored day_open_equity value."""

    @pytest.mark.asyncio
    async def test_reuses_snapshot(self) -> None:
        # Snapshot has day_open=1000, but current equity is 980 (2% drop, no block)
        db = _build_db_no_block(
            day_open_equity=1000.0,
            current_cash=480.0,
            positions_value=500.0,
            snapshot_exists=True,
        )

        allowed, ptype, reason = await _daily_drawdown_guard(db, PORTFOLIO_ID, NOW)

        assert allowed is True
        # db.add should NOT be called (no new snapshot needed, no block event)
        db.add.assert_not_called()


class TestAlreadyBlockedReturnsEarly:
    """When active daily_drawdown event exists, returns blocked without recomputing."""

    @pytest.mark.asyncio
    async def test_already_blocked(self) -> None:
        db = _build_db_already_blocked()

        allowed, ptype, reason = await _daily_drawdown_guard(db, PORTFOLIO_ID, NOW)

        assert allowed is False
        assert ptype == "daily_drawdown"
        assert reason is not None
        assert "circuit breaker active" in reason
        # Only 1 DB call (the active block check) — no equity computation
        assert db.execute.await_count == 1

"""Tests for daily drawdown circuit breaker guard.

Task: marketpulse-task-2026-04-01-0017
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

# Import AnomalyEvent so SQLAlchemy mapper registers it before ProtectionEvent is used
import app.anomalies.models  # noqa: F401

from app.portfolio.protections import (
    DAILY_DD_LIMIT_PCT,
    DAILY_DD_RULE,
    check_daily_drawdown,
    daily_drawdown_guard,
)


# ── Helpers ──────────────────────────────────────────


def _make_scalar_result(value: object) -> MagicMock:
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


PORTFOLIO_ID = uuid.uuid4()
NOW = datetime(2026, 4, 1, 14, 30, 0, tzinfo=timezone.utc)


# ── Pure function tests ──────────────────────────────


class TestDailyDrawdownGuard:
    def test_no_block_when_equity_above_threshold(self) -> None:
        # 4% drop — within 5% limit
        assert daily_drawdown_guard(1000.0, 960.0) is None

    def test_blocks_at_exact_threshold(self) -> None:
        # Exactly 5% drop
        result = daily_drawdown_guard(1000.0, 950.0)
        assert result is not None
        assert result["blocked"] is True
        assert result["rule"] == DAILY_DD_RULE
        assert result["drawdown_pct"] == -0.05

    def test_blocks_below_threshold(self) -> None:
        # 10% drop
        result = daily_drawdown_guard(1000.0, 900.0)
        assert result is not None
        assert result["blocked"] is True
        assert result["drawdown_pct"] == -0.1

    def test_no_block_when_equity_increased(self) -> None:
        assert daily_drawdown_guard(1000.0, 1100.0) is None

    def test_zero_opening_equity_returns_none(self) -> None:
        assert daily_drawdown_guard(0.0, 100.0) is None

    def test_negative_opening_equity_returns_none(self) -> None:
        assert daily_drawdown_guard(-50.0, 100.0) is None

    def test_custom_threshold(self) -> None:
        # 3% drop with 3% threshold
        result = daily_drawdown_guard(1000.0, 970.0, threshold_pct=-0.03)
        assert result is not None
        assert result["blocked"] is True
        assert result["threshold_pct"] == -0.03

    def test_custom_threshold_not_breached(self) -> None:
        # 2% drop with 3% threshold — not breached
        assert daily_drawdown_guard(1000.0, 980.0, threshold_pct=-0.03) is None

    def test_return_dict_has_required_keys(self) -> None:
        result = daily_drawdown_guard(1000.0, 940.0)
        assert result is not None
        expected_keys = {
            "blocked", "rule", "drawdown_pct",
            "threshold_pct", "opening_equity", "current_equity",
        }
        assert set(result.keys()) == expected_keys


# ── Async function tests ─────────────────────────────


class TestCheckDailyDrawdown:
    @pytest.mark.asyncio
    async def test_creates_protection_event_on_breach(self) -> None:
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_make_scalar_result(0))

        blocked = await check_daily_drawdown(
            db, PORTFOLIO_ID, 1000.0, 900.0, now=NOW,
        )

        assert blocked is True
        db.add.assert_called_once()
        event = db.add.call_args[0][0]
        assert event.protection_type == DAILY_DD_RULE
        assert event.status == "active"
        assert "exceeded" in event.reason
        assert event.context_data is not None
        assert event.expires_at is not None

    @pytest.mark.asyncio
    async def test_returns_true_when_already_blocked_today(self) -> None:
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_make_scalar_result(1))

        blocked = await check_daily_drawdown(
            db, PORTFOLIO_ID, 1000.0, 900.0, now=NOW,
        )

        assert blocked is True
        db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_false_when_within_limit(self) -> None:
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_make_scalar_result(0))

        blocked = await check_daily_drawdown(
            db, PORTFOLIO_ID, 1000.0, 980.0, now=NOW,
        )

        assert blocked is False
        db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_event_expires_at_end_of_utc_day(self) -> None:
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_make_scalar_result(0))

        await check_daily_drawdown(
            db, PORTFOLIO_ID, 1000.0, 900.0, now=NOW,
        )

        event = db.add.call_args[0][0]
        expected_eod = datetime(2026, 4, 2, 0, 0, 0, tzinfo=timezone.utc)
        assert event.expires_at == expected_eod

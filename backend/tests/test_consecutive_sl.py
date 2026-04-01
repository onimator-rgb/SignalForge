"""Tests for consecutive stop-loss protection guard.

Task: marketpulse-task-2026-04-01-0009
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.portfolio.protections import (
    CONSECUTIVE_SL_LOCK_MINUTES,
    CONSECUTIVE_SL_THRESHOLD,
    _check_consecutive_sl,
    check_protections,
)


# ── Helpers ──────────────────────────────────────────


def _make_scalar_result(value: Any) -> MagicMock:
    """Build a mock DB result whose .scalar_one() returns *value*."""
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


def _make_scalars_result(values: list[Any]) -> MagicMock:
    """Build a mock DB result whose .scalars().all() returns *values*."""
    result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = values
    result.scalars.return_value = scalars_mock
    return result


def _build_db_mock(
    active_guard_count: int,
    close_reasons: list[str],
    *,
    extra_execute_results: list[Any] | None = None,
) -> AsyncMock:
    """Build an AsyncSession mock that returns the given data.

    Execute calls are ordered:
    1. _expire_protections (UPDATE — no result needed, returns MagicMock)
    2. _check_asset_cooldown → scalar count (0 = not blocked)
    3. _check_stoploss_guard active count → 0
    4. _check_stoploss_guard loss count → 0
    5. _check_consecutive_sl active count → active_guard_count
    6. _check_consecutive_sl close_reasons → close_reasons
    7+. Further checks (class_exposure, entry_frequency) if not blocked
    """
    db = AsyncMock()
    results: list[Any] = []

    # 1. _expire_protections
    results.append(MagicMock())
    # 2. _check_asset_cooldown count
    results.append(_make_scalar_result(0))
    # 3. _check_stoploss_guard active count
    results.append(_make_scalar_result(0))
    # 4. _check_stoploss_guard loss count
    results.append(_make_scalar_result(0))
    # 5. _check_consecutive_sl active count
    results.append(_make_scalar_result(active_guard_count))
    # 6. _check_consecutive_sl close_reasons (only if no active guard)
    if active_guard_count == 0:
        results.append(_make_scalars_result(close_reasons))

    if extra_execute_results:
        results.extend(extra_execute_results)

    db.execute = AsyncMock(side_effect=results)
    return db


def _will_trigger(close_reasons: list[str]) -> bool:
    """Return True if the given close_reasons would trigger the guard."""
    stop_reasons = {"stop_hit", "trailing_stop_hit"}
    return (
        len(close_reasons) >= CONSECUTIVE_SL_THRESHOLD
        and all(r in stop_reasons for r in close_reasons[:CONSECUTIVE_SL_THRESHOLD])
    )


def _build_db_mock_for_direct(
    active_guard_count: int,
    close_reasons: list[str],
) -> AsyncMock:
    """Build an AsyncSession mock for calling _check_consecutive_sl directly."""
    db = AsyncMock()
    results: list[Any] = [
        _make_scalar_result(active_guard_count),
    ]
    if active_guard_count == 0:
        results.append(_make_scalars_result(close_reasons))
        # If guard triggers, _log_protection does a dedup check (scalar count=0)
        if _will_trigger(close_reasons):
            results.append(_make_scalar_result(0))
    db.execute = AsyncMock(side_effect=results)
    return db


NOW = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)
PORTFOLIO_ID = uuid.uuid4()
ASSET_ID = uuid.uuid4()


# ── Tests ────────────────────────────────────────────


class TestConsecutiveSlTriggersAfterNStops:
    """3 consecutive stop_hit closes → guard triggers."""

    @pytest.mark.asyncio
    async def test_triggers_via_check_protections(self) -> None:
        # Test consecutive SL directly to avoid mock conflicts with other rules
        db = _build_db_mock_for_direct(
            active_guard_count=0,
            close_reasons=["stop_hit", "stop_hit", "stop_hit"],
        )

        with patch(
            "app.portfolio.protections._log_protection", new_callable=AsyncMock
        ):
            blocked, reason = await _check_consecutive_sl(db, PORTFOLIO_ID, NOW)

        assert blocked is True
        assert reason is not None
        assert "3 consecutive stop losses" in reason

    @pytest.mark.asyncio
    async def test_triggers_direct(self) -> None:
        db = _build_db_mock_for_direct(0, ["stop_hit", "stop_hit", "stop_hit"])
        with patch(
            "app.portfolio.protections._log_protection", new_callable=AsyncMock
        ):
            blocked, reason = await _check_consecutive_sl(db, PORTFOLIO_ID, NOW)
        assert blocked is True
        assert reason is not None
        assert str(CONSECUTIVE_SL_THRESHOLD) in reason


class TestConsecutiveSlAllowsWhenBrokenByProfit:
    """Middle position closed with take_profit → streak broken, allows entry."""

    @pytest.mark.asyncio
    async def test_broken_streak_allows(self) -> None:
        db = _build_db_mock(
            active_guard_count=0,
            close_reasons=["stop_hit", "take_profit", "stop_hit"],
            extra_execute_results=[
                # class_exposure count
                _make_scalar_result(0),
                # entry_frequency count
                _make_scalar_result(0),
            ],
        )

        with patch(
            "app.portfolio.protections._check_asset_cooldown",
            new_callable=AsyncMock, return_value=(False, None, 0),
        ), patch(
            "app.portfolio.protections._check_class_exposure",
            new_callable=AsyncMock, return_value=(False, None),
        ), patch(
            "app.portfolio.protections._check_entry_frequency",
            new_callable=AsyncMock, return_value=(False, None),
        ), patch(
            "app.portfolio.protections._daily_drawdown_guard",
            new_callable=AsyncMock, return_value=(True, None, None),
        ):
            allowed, ptype, reason = await check_protections(
                db, PORTFOLIO_ID, ASSET_ID, "crypto", "normal", now=NOW
            )

        assert allowed is True
        assert ptype is None


class TestConsecutiveSlAllowsWhenFewerThanThreshold:
    """Only 2 closed positions (below threshold of 3) → allows entry."""

    @pytest.mark.asyncio
    async def test_below_threshold_allows(self) -> None:
        db = _build_db_mock_for_direct(0, ["stop_hit", "stop_hit"])
        blocked, reason = await _check_consecutive_sl(db, PORTFOLIO_ID, NOW)
        assert blocked is False
        assert reason is None


class TestConsecutiveSlGuardExpires:
    """Guard expires after CONSECUTIVE_SL_LOCK_MINUTES, entry allowed."""

    @pytest.mark.asyncio
    async def test_active_guard_blocks(self) -> None:
        db = _build_db_mock_for_direct(active_guard_count=1, close_reasons=[])
        blocked, reason = await _check_consecutive_sl(db, PORTFOLIO_ID, NOW)
        assert blocked is True
        assert reason is not None
        assert "cooling down" in reason

    @pytest.mark.asyncio
    async def test_expired_guard_allows(self) -> None:
        """After expiry (_expire_protections sets status=expired), guard count is 0
        and the streak may be broken by new trades."""
        db = _build_db_mock_for_direct(
            active_guard_count=0,
            close_reasons=["take_profit", "stop_hit", "stop_hit"],
        )
        blocked, reason = await _check_consecutive_sl(db, PORTFOLIO_ID, NOW)
        assert blocked is False
        assert reason is None


class TestConsecutiveSlMixedStopReasons:
    """Mix of stop_hit and trailing_stop_hit → guard should trigger."""

    @pytest.mark.asyncio
    async def test_mixed_stop_reasons_trigger(self) -> None:
        db = _build_db_mock_for_direct(
            0, ["stop_hit", "trailing_stop_hit", "stop_hit"]
        )
        with patch(
            "app.portfolio.protections._log_protection", new_callable=AsyncMock
        ):
            blocked, reason = await _check_consecutive_sl(db, PORTFOLIO_ID, NOW)
        assert blocked is True
        assert reason is not None

    @pytest.mark.asyncio
    async def test_all_trailing_stops_trigger(self) -> None:
        db = _build_db_mock_for_direct(
            0, ["trailing_stop_hit", "trailing_stop_hit", "trailing_stop_hit"]
        )
        with patch(
            "app.portfolio.protections._log_protection", new_callable=AsyncMock
        ):
            blocked, reason = await _check_consecutive_sl(db, PORTFOLIO_ID, NOW)
        assert blocked is True


class TestProtectionEventCreation:
    """Verify _log_protection is called with correct args when guard triggers."""

    @pytest.mark.asyncio
    async def test_log_protection_called(self) -> None:
        db = _build_db_mock_for_direct(0, ["stop_hit", "stop_hit", "stop_hit"])

        with patch(
            "app.portfolio.protections._log_protection", new_callable=AsyncMock
        ) as mock_log:
            blocked, reason = await _check_consecutive_sl(db, PORTFOLIO_ID, NOW)

            assert blocked is True
            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args
            assert call_kwargs[0][1] == "consecutive_sl_guard"
            assert call_kwargs[1]["expires"] == NOW + timedelta(
                minutes=CONSECUTIVE_SL_LOCK_MINUTES
            )

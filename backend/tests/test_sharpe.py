"""Comprehensive tests for daily-return Sharpe ratio calculation."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.portfolio.risk_metrics import _compute_daily_returns, compute_risk_metrics


def _pos(
    pnl_pct: float,
    pnl_usd: float,
    opened_at: datetime | None = None,
    closed_at: datetime | None = None,
    close_reason: str = "manual",
) -> SimpleNamespace:
    """Create a mock closed position."""
    base = datetime(2026, 1, 1, 12, 0)
    return SimpleNamespace(
        realized_pnl_pct=pnl_pct,
        realized_pnl_usd=pnl_usd,
        opened_at=opened_at or base,
        closed_at=closed_at,
        close_reason=close_reason,
    )


class TestDailyReturns:
    """Tests for _compute_daily_returns helper."""

    def test_daily_returns_grouping(self) -> None:
        """5 positions across 3 days, verify grouping and sums."""
        base = datetime(2026, 1, 1, 12, 0)
        day1 = base + timedelta(days=1)
        day2 = base + timedelta(days=2)
        day3 = base + timedelta(days=3)

        positions = [
            _pos(pnl_pct=5.0, pnl_usd=50.0, closed_at=day1),      # day1: +0.05
            _pos(pnl_pct=3.0, pnl_usd=30.0, closed_at=day1),      # day1: +0.03
            _pos(pnl_pct=-2.0, pnl_usd=-20.0, closed_at=day2),    # day2: -0.02
            _pos(pnl_pct=4.0, pnl_usd=40.0, closed_at=day2),      # day2: +0.04
            _pos(pnl_pct=-1.0, pnl_usd=-10.0, closed_at=day3),    # day3: -0.01
        ]

        daily = _compute_daily_returns(positions)
        assert len(daily) == 3
        assert abs(daily[0] - 0.08) < 1e-9   # day1: 0.05 + 0.03
        assert abs(daily[1] - 0.02) < 1e-9   # day2: -0.02 + 0.04
        assert abs(daily[2] - (-0.01)) < 1e-9  # day3: -0.01


class TestSharpeDaily:
    """Tests for Sharpe ratio with daily returns."""

    def test_sharpe_known_values(self) -> None:
        """Positions across 5 days with known returns, verify exact Sharpe."""
        base = datetime(2026, 1, 1, 12, 0)
        # One position per day for simplicity
        returns_pct = [2.0, -1.0, 3.0, -0.5, 1.5]
        positions = [
            _pos(
                pnl_pct=r,
                pnl_usd=r * 10,
                closed_at=base + timedelta(days=i + 1),
            )
            for i, r in enumerate(returns_pct)
        ]

        result = compute_risk_metrics(positions)

        # Manual calculation
        daily = [r / 100 for r in returns_pct]  # [0.02, -0.01, 0.03, -0.005, 0.015]
        mean_d = sum(daily) / len(daily)
        var_d = sum((x - mean_d) ** 2 for x in daily) / (len(daily) - 1)
        std_d = math.sqrt(var_d)
        expected = (mean_d - 0.0 / 252) / std_d * math.sqrt(252)

        assert result.sharpe_ratio is not None
        assert abs(result.sharpe_ratio - round(expected, 4)) < 0.001

    def test_sharpe_with_risk_free_rate(self) -> None:
        """risk_free_rate > 0 should lower the Sharpe ratio."""
        base = datetime(2026, 1, 1, 12, 0)
        returns_pct = [2.0, -1.0, 3.0, -0.5, 1.5]
        positions = [
            _pos(
                pnl_pct=r,
                pnl_usd=r * 10,
                closed_at=base + timedelta(days=i + 1),
            )
            for i, r in enumerate(returns_pct)
        ]

        result_zero = compute_risk_metrics(positions, risk_free_rate=0.0)
        result_rf = compute_risk_metrics(positions, risk_free_rate=0.04)

        assert result_zero.sharpe_ratio is not None
        assert result_rf.sharpe_ratio is not None
        assert result_rf.sharpe_ratio < result_zero.sharpe_ratio

    def test_sharpe_single_day_returns_none(self) -> None:
        """All positions close same day -> 1 daily return -> Sharpe is None."""
        base = datetime(2026, 1, 1, 12, 0)
        same_day = base + timedelta(days=1)
        positions = [
            _pos(pnl_pct=5.0, pnl_usd=50.0, closed_at=same_day),
            _pos(pnl_pct=-3.0, pnl_usd=-30.0, closed_at=same_day),
            _pos(pnl_pct=2.0, pnl_usd=20.0, closed_at=same_day),
        ]
        result = compute_risk_metrics(positions)
        assert result.sharpe_ratio is None

    def test_sharpe_no_positions_none(self) -> None:
        """Empty list -> Sharpe is None."""
        result = compute_risk_metrics([])
        assert result.sharpe_ratio is None

    def test_sharpe_no_closed_at_skipped(self) -> None:
        """Positions with closed_at=None are excluded from daily returns."""
        base = datetime(2026, 1, 1, 12, 0)
        positions = [
            _pos(pnl_pct=5.0, pnl_usd=50.0, closed_at=None),
            _pos(pnl_pct=-3.0, pnl_usd=-30.0, closed_at=None),
            _pos(pnl_pct=2.0, pnl_usd=20.0, closed_at=base + timedelta(days=1)),
        ]
        result = compute_risk_metrics(positions)
        # Only 1 day with closed_at -> Sharpe is None
        assert result.sharpe_ratio is None

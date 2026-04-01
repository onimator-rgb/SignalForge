"""Unit tests for portfolio risk metrics computation."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.portfolio.risk_metrics import compute_risk_metrics


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
        closed_at=closed_at or base + timedelta(hours=24),
        close_reason=close_reason,
    )


class TestComputeRiskMetricsEmpty:
    """Tests for edge cases with no data."""

    def test_empty_positions(self) -> None:
        result = compute_risk_metrics([])
        assert result.total_closed == 0
        assert result.sharpe_ratio is None
        assert result.sortino_ratio is None
        assert result.max_drawdown_pct == 0.0
        assert result.profit_factor is None
        assert result.avg_hold_hours == 0.0
        assert result.wins == 0
        assert result.losses == 0
        assert result.win_rate is None
        assert result.breakdown_by_reason == {}

    def test_single_position_no_ratios(self) -> None:
        """With fewer than 2 trades, Sharpe/Sortino should be None."""
        pos = _pos(pnl_pct=5.0, pnl_usd=50.0, close_reason="take_profit")
        result = compute_risk_metrics([pos])
        assert result.total_closed == 1
        assert result.sharpe_ratio is None
        assert result.sortino_ratio is None
        assert result.wins == 1
        assert result.losses == 0
        assert result.win_rate == 100.0


class TestSharpeRatio:
    """Tests for Sharpe ratio calculation."""

    def test_known_returns(self) -> None:
        """5 trades on 5 different days with returns [5%, -3%, 8%, -2%, 4%]."""
        base = datetime(2026, 1, 1, 12, 0)
        returns_pct = [5.0, -3.0, 8.0, -2.0, 4.0]
        positions = [
            _pos(
                pnl_pct=r,
                pnl_usd=r * 10,
                opened_at=base,
                closed_at=base + timedelta(days=i + 1),
            )
            for i, r in enumerate(returns_pct)
        ]
        result = compute_risk_metrics(positions)

        # Daily returns (one trade per day): [0.05, -0.03, 0.08, -0.02, 0.04]
        daily = [r / 100 for r in returns_pct]
        mean_d = sum(daily) / len(daily)
        var_d = sum((x - mean_d) ** 2 for x in daily) / (len(daily) - 1)
        std_d = math.sqrt(var_d)
        expected_sharpe = (mean_d - 0.0 / 252) / std_d * math.sqrt(252)

        assert result.sharpe_ratio is not None
        assert abs(result.sharpe_ratio - round(expected_sharpe, 4)) < 0.001

    def test_zero_std_returns_none(self) -> None:
        """If all daily returns are identical, std=0 -> Sharpe is None."""
        base = datetime(2026, 1, 1, 12, 0)
        positions = [
            _pos(pnl_pct=3.0, pnl_usd=30.0, closed_at=base + timedelta(days=i + 1))
            for i in range(3)
        ]
        result = compute_risk_metrics(positions)
        assert result.sharpe_ratio is None


class TestSortinoRatio:
    """Tests for Sortino ratio calculation."""

    def test_no_negative_returns(self) -> None:
        """All positive returns -> downside std = 0 -> Sortino is None."""
        positions = [
            _pos(pnl_pct=5.0, pnl_usd=50.0),
            _pos(pnl_pct=3.0, pnl_usd=30.0),
            _pos(pnl_pct=7.0, pnl_usd=70.0),
        ]
        result = compute_risk_metrics(positions)
        assert result.sortino_ratio is None

    def test_mixed_returns(self) -> None:
        """With negative returns, Sortino should be computed."""
        positions = [
            _pos(pnl_pct=5.0, pnl_usd=50.0),
            _pos(pnl_pct=-3.0, pnl_usd=-30.0),
            _pos(pnl_pct=8.0, pnl_usd=80.0),
        ]
        result = compute_risk_metrics(positions)
        assert result.sortino_ratio is not None
        # Sortino should be positive since mean return is positive
        assert result.sortino_ratio > 0


class TestMaxDrawdown:
    """Tests for max drawdown calculation."""

    def test_monotonic_gains(self) -> None:
        """All gains -> 0% drawdown."""
        base = datetime(2026, 1, 1)
        positions = [
            _pos(pnl_pct=5.0, pnl_usd=50.0, closed_at=base + timedelta(hours=i * 24))
            for i in range(3)
        ]
        result = compute_risk_metrics(positions)
        assert result.max_drawdown_pct == 0.0

    def test_peak_to_trough(self) -> None:
        """Sequence: +100, -30, +20 -> peak=100, trough=70, dd=30%."""
        base = datetime(2026, 1, 1)
        positions = [
            _pos(pnl_pct=10.0, pnl_usd=100.0, closed_at=base + timedelta(hours=1)),
            _pos(pnl_pct=-3.0, pnl_usd=-30.0, closed_at=base + timedelta(hours=2)),
            _pos(pnl_pct=2.0, pnl_usd=20.0, closed_at=base + timedelta(hours=3)),
        ]
        result = compute_risk_metrics(positions)
        # Peak = 100, trough after loss = 70, dd = 30/100 = 30%
        assert abs(result.max_drawdown_pct - 30.0) < 0.01

    def test_all_losses(self) -> None:
        """All losses -> 100% drawdown."""
        base = datetime(2026, 1, 1)
        positions = [
            _pos(pnl_pct=-5.0, pnl_usd=-50.0, closed_at=base + timedelta(hours=i))
            for i in range(3)
        ]
        result = compute_risk_metrics(positions)
        assert result.max_drawdown_pct == 100.0


class TestProfitFactor:
    """Tests for profit factor calculation."""

    def test_profit_factor_normal(self) -> None:
        """Gross profit / gross loss."""
        positions = [
            _pos(pnl_pct=5.0, pnl_usd=50.0),
            _pos(pnl_pct=-3.0, pnl_usd=-30.0),
            _pos(pnl_pct=8.0, pnl_usd=80.0),
        ]
        result = compute_risk_metrics(positions)
        # PF = (50 + 80) / 30 = 4.3333
        assert result.profit_factor is not None
        assert abs(result.profit_factor - 4.3333) < 0.01

    def test_no_losses_none(self) -> None:
        """No losses -> profit factor is None (division by zero)."""
        positions = [
            _pos(pnl_pct=5.0, pnl_usd=50.0),
            _pos(pnl_pct=3.0, pnl_usd=30.0),
        ]
        result = compute_risk_metrics(positions)
        assert result.profit_factor is None

    def test_no_profits(self) -> None:
        """No profits -> profit factor = 0."""
        positions = [
            _pos(pnl_pct=-5.0, pnl_usd=-50.0),
            _pos(pnl_pct=-3.0, pnl_usd=-30.0),
        ]
        result = compute_risk_metrics(positions)
        # gross_profit=0, gross_loss=80, PF=0/80=0
        assert result.profit_factor is not None
        assert result.profit_factor == 0.0


class TestBreakdownAndHoldDuration:
    """Tests for breakdown by reason and hold duration."""

    def test_breakdown_by_reason(self) -> None:
        positions = [
            _pos(pnl_pct=5.0, pnl_usd=50.0, close_reason="stop_loss"),
            _pos(pnl_pct=-3.0, pnl_usd=-30.0, close_reason="stop_loss"),
            _pos(pnl_pct=8.0, pnl_usd=80.0, close_reason="take_profit"),
            _pos(pnl_pct=2.0, pnl_usd=20.0, close_reason="max_hold"),
        ]
        result = compute_risk_metrics(positions)
        assert result.breakdown_by_reason == {
            "stop_loss": 2,
            "take_profit": 1,
            "max_hold": 1,
        }

    def test_avg_hold_hours(self) -> None:
        base = datetime(2026, 1, 1)
        positions = [
            _pos(pnl_pct=5.0, pnl_usd=50.0, opened_at=base, closed_at=base + timedelta(hours=10)),
            _pos(pnl_pct=-3.0, pnl_usd=-30.0, opened_at=base, closed_at=base + timedelta(hours=20)),
        ]
        result = compute_risk_metrics(positions)
        assert result.avg_hold_hours == 15.0

    def test_win_rate(self) -> None:
        positions = [
            _pos(pnl_pct=5.0, pnl_usd=50.0),
            _pos(pnl_pct=-3.0, pnl_usd=-30.0),
            _pos(pnl_pct=8.0, pnl_usd=80.0),
            _pos(pnl_pct=-2.0, pnl_usd=-20.0),
        ]
        result = compute_risk_metrics(positions)
        # 2 wins / 4 total = 50%
        assert result.win_rate == 50.0
        assert result.wins == 2
        assert result.losses == 2

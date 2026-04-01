"""Tests for avg win/loss and best/worst trade metrics in risk dashboard."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

from app.portfolio.risk_metrics import compute_risk_metrics


def _pos(
    pnl_pct: float,
    pnl_usd: float,
    opened_at: datetime | None = None,
    closed_at: datetime | None = None,
    close_reason: str = "manual",
) -> SimpleNamespace:
    base = datetime(2026, 1, 1, 12, 0)
    return SimpleNamespace(
        realized_pnl_pct=pnl_pct,
        realized_pnl_usd=pnl_usd,
        opened_at=opened_at or base,
        closed_at=closed_at or base + timedelta(hours=24),
        close_reason=close_reason,
    )


class TestNoPositions:
    """All new fields should be None when there are no positions."""

    def test_empty_returns_none(self) -> None:
        result = compute_risk_metrics([])
        assert result.avg_win_pct is None
        assert result.avg_loss_pct is None
        assert result.best_trade_pct is None
        assert result.worst_trade_pct is None


class TestOnlyWins:
    """When all trades are winners, avg_loss_pct should be None."""

    def test_only_wins(self) -> None:
        positions = [
            _pos(pnl_pct=5.0, pnl_usd=50.0),
            _pos(pnl_pct=10.0, pnl_usd=100.0),
            _pos(pnl_pct=3.0, pnl_usd=30.0),
        ]
        result = compute_risk_metrics(positions)
        assert result.avg_win_pct == 6.0
        assert result.avg_loss_pct is None
        assert result.best_trade_pct == 10.0
        assert result.worst_trade_pct == 3.0


class TestOnlyLosses:
    """When all trades are losers, avg_win_pct should be None."""

    def test_only_losses(self) -> None:
        positions = [
            _pos(pnl_pct=-2.0, pnl_usd=-20.0),
            _pos(pnl_pct=-8.0, pnl_usd=-80.0),
        ]
        result = compute_risk_metrics(positions)
        assert result.avg_win_pct is None
        assert result.avg_loss_pct == -5.0
        assert result.best_trade_pct == -2.0
        assert result.worst_trade_pct == -8.0


class TestMixedTrades:
    """Mixed wins and losses should compute all four fields correctly."""

    def test_mixed(self) -> None:
        positions = [
            _pos(pnl_pct=10.0, pnl_usd=100.0),
            _pos(pnl_pct=-4.0, pnl_usd=-40.0),
            _pos(pnl_pct=6.0, pnl_usd=60.0),
            _pos(pnl_pct=-2.0, pnl_usd=-20.0),
        ]
        result = compute_risk_metrics(positions)
        # avg win = (10+6)/2 = 8.0
        assert result.avg_win_pct == 8.0
        # avg loss = (-4+-2)/2 = -3.0
        assert result.avg_loss_pct == -3.0
        # best = 10, worst = -4
        assert result.best_trade_pct == 10.0
        assert result.worst_trade_pct == -4.0


class TestBestWorstExtremes:
    """Verify best/worst are the correct extremes."""

    def test_extremes(self) -> None:
        positions = [
            _pos(pnl_pct=25.0, pnl_usd=250.0),
            _pos(pnl_pct=-15.0, pnl_usd=-150.0),
            _pos(pnl_pct=3.0, pnl_usd=30.0),
            _pos(pnl_pct=-1.0, pnl_usd=-10.0),
            _pos(pnl_pct=0.5, pnl_usd=5.0),
        ]
        result = compute_risk_metrics(positions)
        assert result.best_trade_pct == 25.0
        assert result.worst_trade_pct == -15.0

    def test_zero_pnl_excluded_from_win_and_loss(self) -> None:
        """A trade with exactly 0% PnL is excluded from both win and loss buckets."""
        positions = [
            _pos(pnl_pct=0.0, pnl_usd=0.0),
            _pos(pnl_pct=5.0, pnl_usd=50.0),
        ]
        result = compute_risk_metrics(positions)
        assert result.avg_win_pct == 5.0
        assert result.avg_loss_pct is None


class TestExistingFieldsUnchanged:
    """Ensure existing metrics are not broken by the new fields."""

    def test_existing_metrics_still_correct(self) -> None:
        positions = [
            _pos(pnl_pct=5.0, pnl_usd=50.0),
            _pos(pnl_pct=-3.0, pnl_usd=-30.0),
        ]
        result = compute_risk_metrics(positions)
        assert result.total_closed == 2
        assert result.wins == 1
        assert result.losses == 1
        assert result.win_rate == 50.0
        # New fields also present
        assert result.avg_win_pct is not None
        assert result.avg_loss_pct is not None

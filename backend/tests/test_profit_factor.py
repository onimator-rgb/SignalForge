"""Dedicated tests for profit factor, avg win/loss, best/worst trade calculations."""

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
    """Create a mock closed position."""
    base = datetime(2026, 1, 1, 12, 0)
    return SimpleNamespace(
        realized_pnl_pct=pnl_pct,
        realized_pnl_usd=pnl_usd,
        opened_at=opened_at or base,
        closed_at=closed_at or base + timedelta(hours=24),
        close_reason=close_reason,
    )


class TestAvgWinLoss:
    """Tests for avg_win_pct and avg_loss_pct calculations."""

    def test_avg_win_pct_multiple_wins(self) -> None:
        positions = [
            _pos(pnl_pct=5.0, pnl_usd=50.0),
            _pos(pnl_pct=10.0, pnl_usd=100.0),
            _pos(pnl_pct=15.0, pnl_usd=150.0),
        ]
        result = compute_risk_metrics(positions)
        assert result.avg_win_pct == 10.0

    def test_avg_loss_pct_multiple_losses(self) -> None:
        positions = [
            _pos(pnl_pct=-3.0, pnl_usd=-30.0),
            _pos(pnl_pct=-6.0, pnl_usd=-60.0),
            _pos(pnl_pct=-9.0, pnl_usd=-90.0),
        ]
        result = compute_risk_metrics(positions)
        assert result.avg_loss_pct == -6.0

    def test_avg_win_none_when_no_wins(self) -> None:
        positions = [
            _pos(pnl_pct=-3.0, pnl_usd=-30.0),
            _pos(pnl_pct=-6.0, pnl_usd=-60.0),
        ]
        result = compute_risk_metrics(positions)
        assert result.avg_win_pct is None

    def test_avg_loss_none_when_no_losses(self) -> None:
        positions = [
            _pos(pnl_pct=5.0, pnl_usd=50.0),
            _pos(pnl_pct=10.0, pnl_usd=100.0),
        ]
        result = compute_risk_metrics(positions)
        assert result.avg_loss_pct is None

    def test_mixed_trades(self) -> None:
        positions = [
            _pos(pnl_pct=5.0, pnl_usd=50.0),
            _pos(pnl_pct=15.0, pnl_usd=150.0),
            _pos(pnl_pct=-4.0, pnl_usd=-40.0),
            _pos(pnl_pct=-8.0, pnl_usd=-80.0),
        ]
        result = compute_risk_metrics(positions)
        assert result.avg_win_pct == 10.0
        assert result.avg_loss_pct == -6.0

    def test_empty_positions(self) -> None:
        result = compute_risk_metrics([])
        assert result.avg_win_pct is None
        assert result.avg_loss_pct is None


class TestBestWorstTrade:
    """Tests for best_trade_pct and worst_trade_pct calculations."""

    def test_best_trade(self) -> None:
        positions = [
            _pos(pnl_pct=5.0, pnl_usd=50.0),
            _pos(pnl_pct=-3.0, pnl_usd=-30.0),
            _pos(pnl_pct=12.0, pnl_usd=120.0),
            _pos(pnl_pct=-1.0, pnl_usd=-10.0),
        ]
        result = compute_risk_metrics(positions)
        assert result.best_trade_pct == 12.0

    def test_worst_trade(self) -> None:
        positions = [
            _pos(pnl_pct=5.0, pnl_usd=50.0),
            _pos(pnl_pct=-3.0, pnl_usd=-30.0),
            _pos(pnl_pct=12.0, pnl_usd=120.0),
            _pos(pnl_pct=-1.0, pnl_usd=-10.0),
        ]
        result = compute_risk_metrics(positions)
        assert result.worst_trade_pct == -3.0

    def test_single_position(self) -> None:
        positions = [_pos(pnl_pct=7.0, pnl_usd=70.0)]
        result = compute_risk_metrics(positions)
        assert result.best_trade_pct == 7.0
        assert result.worst_trade_pct == 7.0

    def test_all_negative(self) -> None:
        positions = [
            _pos(pnl_pct=-2.0, pnl_usd=-20.0),
            _pos(pnl_pct=-5.0, pnl_usd=-50.0),
            _pos(pnl_pct=-8.0, pnl_usd=-80.0),
        ]
        result = compute_risk_metrics(positions)
        assert result.best_trade_pct == -2.0
        assert result.worst_trade_pct == -8.0

    def test_empty(self) -> None:
        result = compute_risk_metrics([])
        assert result.best_trade_pct is None
        assert result.worst_trade_pct is None


class TestProfitFactorExtended:
    """Extended profit factor tests with avg metrics consistency."""

    def test_profit_factor_with_avg_metrics(self) -> None:
        positions = [
            _pos(pnl_pct=10.0, pnl_usd=100.0),
            _pos(pnl_pct=20.0, pnl_usd=200.0),
            _pos(pnl_pct=-5.0, pnl_usd=-50.0),
            _pos(pnl_pct=-15.0, pnl_usd=-150.0),
        ]
        result = compute_risk_metrics(positions)
        # profit_factor = (100+200) / (50+150) = 1.5
        assert result.profit_factor is not None
        assert abs(result.profit_factor - 1.5) < 0.001
        assert result.avg_win_pct == 15.0
        assert result.avg_loss_pct == -10.0

    def test_breakeven_trade_excluded_from_avg(self) -> None:
        """Trade with pnl_usd=0.0 should not count as win or loss for avg."""
        positions = [
            _pos(pnl_pct=10.0, pnl_usd=100.0),
            _pos(pnl_pct=0.0, pnl_usd=0.0),
            _pos(pnl_pct=-5.0, pnl_usd=-50.0),
        ]
        result = compute_risk_metrics(positions)
        # Breakeven trade (pnl_usd=0) excluded from win/loss averages
        assert result.avg_win_pct == 10.0
        assert result.avg_loss_pct == -5.0
        assert result.wins == 1
        assert result.losses == 1

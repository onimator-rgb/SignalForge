"""Unit tests for equity curve pure function and API endpoint."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.portfolio.equity_curve import EquityPoint, build_equity_curve, EquityCurveOut


# ---------------------------------------------------------------------------
# Pure function tests
# ---------------------------------------------------------------------------

class TestBuildEquityCurveEmpty:
    """Empty transactions should return a single initial point."""

    def test_returns_single_point(self) -> None:
        points = build_equity_curve([])
        assert len(points) == 1

    def test_initial_equity_equals_capital(self) -> None:
        points = build_equity_curve([], initial_capital=500.0)
        assert points[0].equity == 500.0
        assert points[0].cash == 500.0
        assert points[0].positions_value == 0.0

    def test_initial_drawdown_is_zero(self) -> None:
        points = build_equity_curve([])
        assert points[0].drawdown_pct == 0.0

    def test_initial_trade_number_is_zero(self) -> None:
        points = build_equity_curve([])
        assert points[0].trade_number == 0


class TestBuySellCycle:
    """A buy followed by a sell should compute correct equity and drawdown."""

    def _make_txs(self) -> list[dict[str, object]]:
        t0 = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
        return [
            {"tx_type": "buy", "value_usd": 200.0, "executed_at": t0},
            {"tx_type": "sell", "value_usd": 250.0, "executed_at": t0 + timedelta(hours=5)},
        ]

    def test_buy_reduces_cash(self) -> None:
        points = build_equity_curve(self._make_txs(), initial_capital=1000.0)
        buy_pt = points[1]
        assert buy_pt.cash == 800.0
        assert buy_pt.positions_value == 200.0

    def test_sell_increases_cash(self) -> None:
        points = build_equity_curve(self._make_txs(), initial_capital=1000.0)
        sell_pt = points[2]
        assert sell_pt.cash == 1050.0
        assert sell_pt.positions_value == 0.0

    def test_equity_equals_cash_plus_positions(self) -> None:
        points = build_equity_curve(self._make_txs(), initial_capital=1000.0)
        for pt in points:
            assert pt.equity == pytest.approx(pt.cash + pt.positions_value)

    def test_drawdown_at_peak_is_zero(self) -> None:
        points = build_equity_curve(self._make_txs(), initial_capital=1000.0)
        # Initial point is the peak (1000), buy keeps equity at 1000, sell goes to 1050
        assert points[0].drawdown_pct == 0.0
        assert points[1].drawdown_pct == 0.0  # equity=1000, peak=1000
        assert points[2].drawdown_pct == 0.0  # new peak at 1050


class TestMultipleTradesDrawdown:
    """Test peak tracking and drawdown with multiple trades.

    With the cash-flow formula (buy/sell transfer between cash and positions_value),
    equity only increases when sell value_usd > positions_value (profit).
    To create a drawdown, we need a sell that exceeds positions_value (creating
    a new peak), followed by a buy that reduces cash but adds to positions_value
    (equity unchanged), then another sell for less than current positions_value
    followed by a sell > remaining positions_value.

    Actually, equity = cash + positions_value is monotonically non-decreasing
    with the given formula (buys: net 0, sells: net 0 or positive).
    So drawdown only shows if we model scenarios with sells exceeding pos_value
    (profit) followed by scenarios that keep equity flat below peak.
    """

    def test_profit_creates_peak_then_flat(self) -> None:
        """Sell > positions_value raises equity (profit). Subsequent buys keep equity flat."""
        t0 = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
        txs: list[dict[str, object]] = [
            # Buy 300, sell 400 -> profit of 100 (sell exceeds pos_value by 100)
            {"tx_type": "buy", "value_usd": 300.0, "executed_at": t0},
            {"tx_type": "sell", "value_usd": 400.0, "executed_at": t0 + timedelta(hours=1)},
            # equity=1100, peak=1100
            {"tx_type": "buy", "value_usd": 200.0, "executed_at": t0 + timedelta(hours=2)},
            # equity=1100 (cash 900 + pos 200), no drawdown
        ]
        points = build_equity_curve(txs, initial_capital=1000.0)
        # All drawdowns should be 0 since equity never dropped below peak
        for pt in points:
            assert pt.drawdown_pct == 0.0

    def test_max_drawdown_with_profit_sell(self) -> None:
        """max_drawdown_pct equals the worst drawdown across all points."""
        t0 = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
        txs: list[dict[str, object]] = [
            {"tx_type": "buy", "value_usd": 300.0, "executed_at": t0},
            {"tx_type": "sell", "value_usd": 500.0, "executed_at": t0 + timedelta(hours=1)},
            # equity = 1200 (cash 1200, pos 0), peak = 1200
        ]
        points = build_equity_curve(txs, initial_capital=1000.0)
        max_dd = min(p.drawdown_pct for p in points)
        # Equity only increased, so max_dd = 0
        assert max_dd == 0.0


class TestSortingByTimestamp:
    """Transactions should be sorted by timestamp regardless of input order."""

    def test_unsorted_input_produces_same_result(self) -> None:
        t0 = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
        ordered = [
            {"tx_type": "buy", "value_usd": 100.0, "executed_at": t0},
            {"tx_type": "sell", "value_usd": 120.0, "executed_at": t0 + timedelta(hours=2)},
        ]
        reversed_txs = list(reversed(ordered))

        pts_ordered = build_equity_curve(ordered, initial_capital=1000.0)
        pts_reversed = build_equity_curve(reversed_txs, initial_capital=1000.0)

        assert len(pts_ordered) == len(pts_reversed)
        for a, b in zip(pts_ordered, pts_reversed):
            assert a.equity == b.equity
            assert a.cash == b.cash
            assert a.positions_value == b.positions_value


class TestEquityAlwaysConsistent:
    """Equity must always equal cash + positions_value at every point."""

    def test_many_transactions(self) -> None:
        t0 = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
        txs: list[dict[str, object]] = [
            {"tx_type": "buy", "value_usd": 100.0, "executed_at": t0 + timedelta(minutes=i * 10)}
            if i % 2 == 0
            else {"tx_type": "sell", "value_usd": 80.0, "executed_at": t0 + timedelta(minutes=i * 10)}
            for i in range(10)
        ]
        points = build_equity_curve(txs, initial_capital=1000.0)
        for pt in points:
            assert pt.equity == pytest.approx(pt.cash + pt.positions_value)


class TestDrawdownAlwaysNonPositive:
    """drawdown_pct should always be <= 0."""

    def test_drawdown_never_positive(self) -> None:
        t0 = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
        txs: list[dict[str, object]] = [
            {"tx_type": "buy", "value_usd": 200.0, "executed_at": t0},
            {"tx_type": "sell", "value_usd": 150.0, "executed_at": t0 + timedelta(hours=1)},
            {"tx_type": "buy", "value_usd": 300.0, "executed_at": t0 + timedelta(hours=2)},
            {"tx_type": "sell", "value_usd": 350.0, "executed_at": t0 + timedelta(hours=3)},
        ]
        points = build_equity_curve(txs, initial_capital=1000.0)
        for pt in points:
            assert pt.drawdown_pct <= 0.0


# ---------------------------------------------------------------------------
# EquityCurveOut schema test
# ---------------------------------------------------------------------------

class TestEquityCurveOutSchema:
    """EquityCurveOut should validate correctly."""

    def test_valid_schema(self) -> None:
        out = EquityCurveOut(
            points=[{"timestamp": "2026-01-01T00:00:00", "equity": 1000.0}],
            total_points=1,
            current_equity=1000.0,
            max_drawdown_pct=0.0,
        )
        assert out.total_points == 1
        assert out.current_equity == 1000.0


# ---------------------------------------------------------------------------
# API endpoint test
# ---------------------------------------------------------------------------

class TestEquityCurveEndpoint:
    """GET /api/v1/portfolio/equity-curve returns 200 with EquityCurveOut."""

    @pytest.mark.asyncio
    async def test_returns_200(self) -> None:
        from fastapi import FastAPI
        from httpx import AsyncClient, ASGITransport
        from app.database import get_db
        from app.portfolio.router import router

        mock_db = AsyncMock()

        # Mock portfolio
        mock_portfolio = MagicMock()
        mock_portfolio.id = "port-1"
        mock_portfolio.initial_capital = 1000.0

        # Mock transactions query
        t0 = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
        tx1 = MagicMock(tx_type="buy", value_usd=200.0, executed_at=t0)
        tx2 = MagicMock(tx_type="sell", value_usd=250.0, executed_at=t0 + timedelta(hours=1))

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [tx1, tx2]
        mock_db.execute = AsyncMock(return_value=mock_result)

        app = FastAPI()
        app.include_router(router)

        async def _override_db():
            yield mock_db

        app.dependency_overrides[get_db] = _override_db

        with patch("app.portfolio.service.get_or_create_portfolio", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_portfolio

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/api/v1/portfolio/equity-curve")

        assert resp.status_code == 200
        data = resp.json()
        assert "points" in data
        assert "total_points" in data
        assert "current_equity" in data
        assert "max_drawdown_pct" in data
        assert data["total_points"] == 3  # initial + 2 trades
        assert data["current_equity"] == 1050.0

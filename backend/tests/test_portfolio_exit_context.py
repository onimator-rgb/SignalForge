"""Test that open positions include exit_context in portfolio summary."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.portfolio.service import get_portfolio_summary


def _make_position(**overrides):
    """Build a mock PortfolioPosition with sensible defaults."""
    pos = MagicMock()
    pos.id = overrides.get("id", str(uuid.uuid4()))
    pos.asset_id = overrides.get("asset_id", str(uuid.uuid4()))
    pos.portfolio_id = overrides.get("portfolio_id", str(uuid.uuid4()))
    pos.recommendation_id = overrides.get("recommendation_id", None)
    pos.entry_price = Decimal("100.00")
    pos.quantity = Decimal("1.0")
    pos.entry_value_usd = Decimal("100.00")
    pos.opened_at = datetime.now(timezone.utc) - timedelta(hours=5)
    pos.max_hold_until = datetime.now(timezone.utc) + timedelta(hours=43)
    pos.stop_loss_price = Decimal("95.00")
    pos.take_profit_price = Decimal("110.00")
    pos.peak_price = Decimal("105.00")
    pos.peak_pnl_pct = Decimal("5.0")
    pos.trailing_stop_price = Decimal("98.00")
    pos.break_even_armed = True
    pos.status = "open"
    pos.exit_context = overrides.get(
        "exit_context",
        {"trailing_tp_armed": True, "trailing_tp_peak": 106.5, "entry_slippage": {"market_price": 100.5, "slippage_pct": 0.005, "adjusted_price": 100.0}},
    )
    return pos


def _make_row(pos, symbol="BTC", asset_class="crypto"):
    """Wrap position in a row-like object mimicking SQLAlchemy result."""
    row = MagicMock()
    row.PortfolioPosition = pos
    row.symbol = symbol
    row.asset_class = asset_class
    row.rec_score = None
    row.rec_type = None
    row.rec_rationale = None
    row.rec_version = None
    return row


@pytest.mark.asyncio
async def test_open_position_includes_exit_context():
    """get_portfolio_summary must include exit_context for open positions."""
    portfolio = MagicMock()
    portfolio.id = str(uuid.uuid4())
    portfolio.current_cash = Decimal("9000.00")
    portfolio.initial_capital = Decimal("10000.00")
    portfolio.is_active = True

    pos = _make_position(portfolio_id=portfolio.id)
    row = _make_row(pos)

    # Mock DB session
    db = AsyncMock()

    # First call: get_or_create_portfolio -> select Portfolio
    portfolio_result = MagicMock()
    portfolio_result.scalar_one_or_none.return_value = portfolio

    # Second call: open positions
    open_result = MagicMock()
    open_result.all.return_value = [row]

    # Third call: closed positions
    closed_result = MagicMock()
    closed_result.all.return_value = []

    # Fourth call: transactions
    tx_result = MagicMock()
    tx_result.all.return_value = []

    # Fifth call: all closed for stats
    all_closed_result = MagicMock()
    all_closed_scalars = MagicMock()
    all_closed_scalars.all.return_value = []
    all_closed_result.scalars.return_value = all_closed_scalars

    db.execute = AsyncMock(side_effect=[
        portfolio_result, open_result, closed_result, tx_result, all_closed_result,
    ])

    # Mock get_latest_price
    price_data = MagicMock()
    price_data.close = 102.0

    with patch("app.portfolio.service.get_latest_price", return_value=price_data):
        summary = await get_portfolio_summary(db)

    open_pos = summary["open_positions"]
    assert len(open_pos) == 1

    p = open_pos[0]
    assert "exit_context" in p, "Open position must include exit_context key"
    assert p["exit_context"] is not None
    assert p["exit_context"]["trailing_tp_armed"] is True
    assert p["exit_context"]["trailing_tp_peak"] == 106.5
    assert "entry_slippage" in p["exit_context"]


@pytest.mark.asyncio
async def test_open_position_exit_context_none():
    """exit_context should be None when position has no exit context."""
    portfolio = MagicMock()
    portfolio.id = str(uuid.uuid4())
    portfolio.current_cash = Decimal("9000.00")
    portfolio.initial_capital = Decimal("10000.00")

    pos = _make_position(portfolio_id=portfolio.id, exit_context=None)
    row = _make_row(pos)

    db = AsyncMock()

    portfolio_result = MagicMock()
    portfolio_result.scalar_one_or_none.return_value = portfolio

    open_result = MagicMock()
    open_result.all.return_value = [row]

    closed_result = MagicMock()
    closed_result.all.return_value = []

    tx_result = MagicMock()
    tx_result.all.return_value = []

    all_closed_result = MagicMock()
    all_closed_scalars = MagicMock()
    all_closed_scalars.all.return_value = []
    all_closed_result.scalars.return_value = all_closed_scalars

    db.execute = AsyncMock(side_effect=[
        portfolio_result, open_result, closed_result, tx_result, all_closed_result,
    ])

    price_data = MagicMock()
    price_data.close = 102.0

    with patch("app.portfolio.service.get_latest_price", return_value=price_data):
        summary = await get_portfolio_summary(db)

    p = summary["open_positions"][0]
    assert "exit_context" in p
    assert p["exit_context"] is None

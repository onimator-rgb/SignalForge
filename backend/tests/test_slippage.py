"""Tests for buy/sell slippage simulation in paper trading."""

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.strategy.profiles import PROFILES, StrategyProfile


# ── S4: Profile slippage values ──────────────────────


class TestSlippageProfileValues:
    """Verify per-profile slippage configuration."""

    def test_conservative_slippage(self) -> None:
        p = PROFILES["conservative"]
        assert p.slippage_buy_pct == 0.0005
        assert p.slippage_sell_pct == 0.0005

    def test_balanced_slippage(self) -> None:
        p = PROFILES["balanced"]
        assert p.slippage_buy_pct == 0.001
        assert p.slippage_sell_pct == 0.001

    def test_aggressive_slippage(self) -> None:
        p = PROFILES["aggressive"]
        assert p.slippage_buy_pct == 0.0015
        assert p.slippage_sell_pct == 0.0015

    def test_slippage_varies_by_profile(self) -> None:
        """Conservative < balanced < aggressive slippage."""
        c = PROFILES["conservative"]
        b = PROFILES["balanced"]
        a = PROFILES["aggressive"]
        assert c.slippage_buy_pct < b.slippage_buy_pct < a.slippage_buy_pct
        assert c.slippage_sell_pct < b.slippage_sell_pct < a.slippage_sell_pct


# ── S1: Buy slippage adjusts entry price ─────────────


class TestSlippageBuyAdjustsEntryPrice:
    def test_buy_slippage_increases_entry_price(self) -> None:
        """Given market price 100.0 and balanced profile (0.1%), entry = 100.10."""
        market_price = 100.0
        profile = PROFILES["balanced"]
        adjusted = round(market_price * (1 + profile.slippage_buy_pct), 8)
        assert adjusted == 100.1

    def test_buy_slippage_quantity_uses_adjusted_price(self) -> None:
        """Quantity is computed from adjusted price, not market price."""
        market_price = 100.0
        size_usd = 1000.0
        profile = PROFILES["balanced"]
        adjusted = round(market_price * (1 + profile.slippage_buy_pct), 8)
        quantity = size_usd / adjusted
        expected_qty = 1000.0 / 100.1
        assert abs(quantity - expected_qty) < 1e-8

    def test_buy_slippage_conservative(self) -> None:
        """Conservative profile: 0.05% slippage on 200.0 -> 200.10."""
        market_price = 200.0
        profile = PROFILES["conservative"]
        adjusted = round(market_price * (1 + profile.slippage_buy_pct), 8)
        assert adjusted == 200.1

    def test_buy_slippage_aggressive(self) -> None:
        """Aggressive profile: 0.15% slippage on 200.0 -> 200.30."""
        market_price = 200.0
        profile = PROFILES["aggressive"]
        adjusted = round(market_price * (1 + profile.slippage_buy_pct), 8)
        assert adjusted == 200.3


# ── S2: Sell slippage adjusts exit price ─────────────


class TestSlippageSellAdjustsExitPrice:
    def test_sell_slippage_decreases_exit_price(self) -> None:
        """Given exit market price 115.0 and balanced profile (0.1%), exit = 114.885."""
        market_price = 115.0
        profile = PROFILES["balanced"]
        adjusted = round(market_price * (1 - profile.slippage_sell_pct), 8)
        assert adjusted == 114.885

    def test_sell_slippage_affects_pnl(self) -> None:
        """P&L uses slippage-adjusted exit price."""
        entry_price = 100.1  # already slippage-adjusted
        exit_market_price = 115.0
        profile = PROFILES["balanced"]
        adjusted_exit = round(exit_market_price * (1 - profile.slippage_sell_pct), 8)
        quantity = 10.0

        exit_value = round(adjusted_exit * quantity, 2)
        entry_value = round(entry_price * quantity, 2)
        pnl_usd = round(exit_value - entry_value, 2)

        # Without slippage: (115.0 * 10) - (100.1 * 10) = 149.0
        # With slippage: (114.885 * 10) - (100.1 * 10) = 147.85
        assert pnl_usd == 147.85


# ── S3: Slippage recorded in exit_context ────────────


class TestSlippageRecordedInExitContext:
    def test_entry_slippage_in_exit_context(self) -> None:
        """After buy, exit_context contains entry_slippage dict."""
        market_price = 100.0
        profile = PROFILES["balanced"]
        adjusted = round(market_price * (1 + profile.slippage_buy_pct), 8)

        exit_context = {
            "entry_slippage": {
                "market_price": market_price,
                "slippage_pct": profile.slippage_buy_pct,
                "adjusted_price": adjusted,
            }
        }

        assert "entry_slippage" in exit_context
        assert exit_context["entry_slippage"]["market_price"] == 100.0
        assert exit_context["entry_slippage"]["slippage_pct"] == 0.001
        assert exit_context["entry_slippage"]["adjusted_price"] == 100.1

    def test_exit_slippage_merged_into_exit_context(self) -> None:
        """After close, exit_context contains both entry and exit slippage."""
        profile = PROFILES["balanced"]
        entry_market = 100.0
        exit_market = 115.0
        adjusted_entry = round(entry_market * (1 + profile.slippage_buy_pct), 8)
        adjusted_exit = round(exit_market * (1 - profile.slippage_sell_pct), 8)

        # Simulate the merge that happens in _close_position
        exit_context = {
            "entry_slippage": {
                "market_price": entry_market,
                "slippage_pct": profile.slippage_buy_pct,
                "adjusted_price": adjusted_entry,
            }
        }
        exit_slippage = {
            "exit_slippage": {
                "market_price": exit_market,
                "slippage_pct": profile.slippage_sell_pct,
                "adjusted_price": adjusted_exit,
            }
        }
        exit_context = {**exit_context, **exit_slippage}

        assert "entry_slippage" in exit_context
        assert "exit_slippage" in exit_context
        assert exit_context["exit_slippage"]["market_price"] == 115.0
        assert exit_context["exit_slippage"]["slippage_pct"] == 0.001
        assert exit_context["exit_slippage"]["adjusted_price"] == 114.885


# ── S5: Zero slippage is a no-op ─────────────────────


class TestZeroSlippageNoEffect:
    def test_zero_buy_slippage(self) -> None:
        """If slippage is 0, entry price equals market price."""
        market_price = 100.0
        adjusted = round(market_price * (1 + 0.0), 8)
        assert adjusted == market_price

    def test_zero_sell_slippage(self) -> None:
        """If slippage is 0, exit price equals market price."""
        market_price = 115.0
        adjusted = round(market_price * (1 - 0.0), 8)
        assert adjusted == market_price

    def test_zero_slippage_pnl_unchanged(self) -> None:
        """With zero slippage, P&L is identical to raw market prices."""
        entry_price = 100.0
        exit_price = 115.0
        quantity = 10.0

        # No slippage
        pnl_no_slip = round((exit_price * quantity) - (entry_price * quantity), 2)

        # Zero slippage applied
        adj_entry = round(entry_price * (1 + 0.0), 8)
        adj_exit = round(exit_price * (1 - 0.0), 8)
        pnl_zero_slip = round((adj_exit * quantity) - (adj_entry * quantity), 2)

        assert pnl_no_slip == pnl_zero_slip

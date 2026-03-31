"""Tests for trailing take profit exit logic.

Task: marketpulse-task-2026-03-31-0003
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from app.portfolio.exits import evaluate_exit, update_position_state
from app.strategy.profiles import PROFILES


def _make_position(
    entry_price: float = 100.0,
    peak_price: float | None = None,
    peak_pnl_pct: float | None = None,
    trailing_stop_price: float | None = None,
    break_even_armed: bool = False,
    exit_context: dict[str, Any] | None = None,
    max_hold_until: datetime | None = None,
) -> Any:
    """Build a lightweight position object for unit tests (no DB)."""
    return SimpleNamespace(
        entry_price=entry_price,
        peak_price=peak_price or entry_price,
        peak_pnl_pct=peak_pnl_pct or 0.0,
        trailing_stop_price=trailing_stop_price,
        break_even_armed=break_even_armed,
        exit_context=exit_context,
        max_hold_until=max_hold_until,
    )


BALANCED = PROFILES["balanced"]
# balanced: take_profit_pct=0.15, trailing_pct=0.05, trailing_arm_pct=0.06
# Arm threshold = take_profit_pct + trailing_arm_pct = 0.15 + 0.06 = 0.21 (21%)
# Trailing stop after arm = peak * (1 - trailing_pct) = peak * 0.95
# Safety floor = entry * (1 + take_profit_pct) = entry * 1.15


class TestTpImmediateCloseBelowArm:
    """Price hits take_profit but below arm threshold → immediate close."""

    def test_tp_immediate_close_below_arm(self) -> None:
        pos = _make_position(entry_price=100.0, peak_price=100.0)
        # 18% gain — above take_profit (15%) but below arm (21%)
        current_price = 118.0
        reason, ctx = evaluate_exit(pos, current_price, BALANCED, regime="normal")
        assert reason == "target_hit"
        assert ctx["rule"] == "take_profit"


class TestTpArmsTrailingAboveArm:
    """Price hits arm threshold → does NOT close, trailing armed."""

    def test_tp_arms_trailing_above_arm(self) -> None:
        pos = _make_position(entry_price=100.0, peak_price=100.0)
        # 22% gain — above arm threshold (21%)
        current_price = 122.0
        reason, ctx = evaluate_exit(pos, current_price, BALANCED, regime="normal")
        assert reason is None, f"Expected no close, got reason={reason}"
        assert ctx.get("trailing_tp_armed") is True


class TestTrailingTpClosesOnRetracement:
    """After arming, price drops trailing_pct from peak → closes."""

    def test_trailing_tp_closes_on_retracement(self) -> None:
        # Position already armed with peak at 130
        pos = _make_position(
            entry_price=100.0,
            peak_price=130.0,
            exit_context={"trailing_tp_armed": True, "trailing_tp_peak": 130.0},
        )
        # Trailing TP stop = max(130 * (1 - 0.05), 100 * 1.15) = max(123.5, 115.0) = 123.5
        # Price drops to 123.0 — below 123.5
        current_price = 123.0
        reason, ctx = evaluate_exit(pos, current_price, BALANCED, regime="normal")
        assert reason == "trailing_tp_hit"
        assert ctx["rule"] == "trailing_tp"
        assert ctx["trailing_tp_stop"] == pytest.approx(123.5)


class TestTrailingTpTracksPeak:
    """Price continues rising after arm, peak is updated in exit_context."""

    def test_trailing_tp_tracks_peak(self) -> None:
        pos = _make_position(
            entry_price=100.0,
            peak_price=122.0,
            exit_context={"trailing_tp_armed": True, "trailing_tp_peak": 122.0},
        )
        # Price rises to 130 — should update peak
        current_price = 130.0
        changed = update_position_state(pos, current_price, BALANCED, regime="normal")
        assert changed is True
        assert pos.exit_context["trailing_tp_peak"] == 130.0


class TestTrailingTpSafetyFloor:
    """Trailing TP exit price never falls below take_profit_price."""

    def test_trailing_tp_safety_floor(self) -> None:
        # Entry=100, take_profit_price = 115.0
        # Peak=118, trailing raw = 118 * 0.95 = 112.1 < 115.0
        # Safety floor should clamp UP to take_profit_price
        pos = _make_position(
            entry_price=100.0,
            peak_price=118.0,
            exit_context={"trailing_tp_armed": True, "trailing_tp_peak": 118.0},
        )
        take_profit_price = 100.0 * (1 + BALANCED.take_profit_pct)
        # Check floor at a price well above floor — should NOT close
        reason, ctx = evaluate_exit(pos, 118.0, BALANCED, regime="normal")
        assert ctx["trailing_tp_stop"] == pytest.approx(take_profit_price)
        assert reason is None

    def test_trailing_tp_floor_triggers_close(self) -> None:
        """Price drops below floor level -> trailing TP fires."""
        pos = _make_position(
            entry_price=100.0,
            peak_price=118.0,
            exit_context={"trailing_tp_armed": True, "trailing_tp_peak": 118.0},
        )
        take_profit_price = 100.0 * (1 + BALANCED.take_profit_pct)
        # Price clearly below safety floor
        current_price = take_profit_price - 0.50
        reason, ctx = evaluate_exit(pos, current_price, BALANCED, regime="normal")
        assert ctx["trailing_tp_stop"] == pytest.approx(take_profit_price)
        assert reason == "trailing_tp_hit"


class TestTrailingTpDoesNotOverrideStopLoss:
    """Stop loss still triggers first even when trailing-TP is armed."""

    def test_trailing_tp_does_not_override_stop_loss(self) -> None:
        pos = _make_position(
            entry_price=100.0,
            peak_price=130.0,
            exit_context={"trailing_tp_armed": True, "trailing_tp_peak": 130.0},
        )
        # Price crashes to 91 — below stop loss (-9%)
        current_price = 91.0
        reason, ctx = evaluate_exit(pos, current_price, BALANCED, regime="normal")
        assert reason == "stop_hit"
        assert ctx["rule"] == "stop_loss"


class TestTrailingTpRegimeAdjustment:
    """In risk_off regime, trailing-TP arm threshold is adjusted."""

    def test_trailing_tp_regime_adjustment(self) -> None:
        pos = _make_position(entry_price=100.0, peak_price=100.0)
        # Normal arm threshold = 0.15 + 0.06 = 0.21
        # risk_off lowers trailing_arm by 1%: effective = 0.05
        # So arm threshold = 0.15 + 0.05 = 0.20
        # 20.5% gain — above risk_off threshold (20%) but below normal (21%)
        current_price = 120.5

        # In risk_off: should arm (20.5% >= 20%)
        changed = update_position_state(pos, current_price, BALANCED, regime="risk_off")
        assert changed is True
        assert pos.exit_context is not None
        assert pos.exit_context.get("trailing_tp_armed") is True

    def test_trailing_tp_not_armed_normal_regime_same_price(self) -> None:
        pos = _make_position(entry_price=100.0, peak_price=100.0)
        current_price = 120.5
        # In normal regime: 20.5% < 21% threshold → NOT armed, just target_hit
        reason, ctx = evaluate_exit(pos, current_price, BALANCED, regime="normal")
        # 20.5% > take_profit (15%) but < arm (21%) → immediate close
        assert reason == "target_hit"

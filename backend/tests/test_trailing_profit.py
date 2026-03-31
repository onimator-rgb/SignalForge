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
# balanced: take_profit_pct=0.15, trailing_tp_pct=0.03, trailing_tp_arm_pct=0.02
# So arm threshold = 0.15 + 0.02 = 0.17 (17% above entry)


class TestTpImmediateCloseBelowArm:
    """S3 test 1: position hits take_profit_pct but not arm threshold → immediate close."""

    def test_tp_immediate_close_below_arm(self) -> None:
        pos = _make_position(entry_price=100.0)
        # 16% gain — above take_profit (15%) but below arm threshold (17%)
        current_price = 116.0
        reason, ctx = evaluate_exit(pos, current_price, BALANCED, regime="normal")
        assert reason == "target_hit"
        assert ctx["rule"] == "take_profit"


class TestTpArmsTrailingAboveArm:
    """S3 test 2: position hits arm threshold → does NOT close, context shows armed."""

    def test_tp_arms_trailing_above_arm(self) -> None:
        pos = _make_position(entry_price=100.0, peak_price=100.0)
        # 18% gain — above arm threshold (17%)
        current_price = 118.0
        reason, ctx = evaluate_exit(pos, current_price, BALANCED, regime="normal")
        assert reason is None, f"Expected no close, got reason={reason}"
        assert ctx.get("trailing_tp_armed") is True


class TestTrailingTpClosesOnRetracement:
    """S3 test 3: after arming, price drops trailing_tp_pct from peak → closes."""

    def test_trailing_tp_closes_on_retracement(self) -> None:
        # Position already armed with peak at 120
        pos = _make_position(
            entry_price=100.0,
            peak_price=120.0,
            exit_context={"trailing_tp_armed": True, "trailing_tp_peak": 120.0},
        )
        # Trailing TP stop = max(120 * (1 - 0.03), 100 * 1.15) = max(116.4, 115.0) = 116.4
        # Price drops to 116.0 — below 116.4
        current_price = 116.0
        reason, ctx = evaluate_exit(pos, current_price, BALANCED, regime="normal")
        assert reason == "trailing_tp_hit"
        assert ctx["rule"] == "trailing_tp"
        assert ctx["trailing_tp_stop"] == pytest.approx(116.4)


class TestTrailingTpTracksPeak:
    """S3 test 4: price continues rising after arm, peak is updated in exit_context."""

    def test_trailing_tp_tracks_peak(self) -> None:
        pos = _make_position(
            entry_price=100.0,
            peak_price=118.0,
            exit_context={"trailing_tp_armed": True, "trailing_tp_peak": 118.0},
        )
        # Price rises to 125 — should update peak
        current_price = 125.0
        changed = update_position_state(pos, current_price, BALANCED, regime="normal")
        assert changed is True
        assert pos.exit_context["trailing_tp_peak"] == 125.0


class TestTrailingTpSafetyFloor:
    """S3 test 5: trailing TP exit price never falls below take_profit_price."""

    def test_trailing_tp_safety_floor(self) -> None:
        # Entry=100, take_profit_price ~ 115.0
        # Peak=118, trailing raw = 118 * 0.97 = 114.46 < ~115
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
    """S3 test 6: stop loss still triggers first even when trailing-TP is armed."""

    def test_trailing_tp_does_not_override_stop_loss(self) -> None:
        # balanced stop_loss_pct = -0.08
        pos = _make_position(
            entry_price=100.0,
            peak_price=120.0,
            exit_context={"trailing_tp_armed": True, "trailing_tp_peak": 120.0},
        )
        # Price crashes to 91 — below stop loss (-9%)
        current_price = 91.0
        reason, ctx = evaluate_exit(pos, current_price, BALANCED, regime="normal")
        assert reason == "stop_hit"
        assert ctx["rule"] == "stop_loss"


class TestTrailingTpRegimeAdjustment:
    """S3 test 7: in risk_off regime, trailing-TP arm threshold is lowered."""

    def test_trailing_tp_regime_adjustment(self) -> None:
        pos = _make_position(entry_price=100.0, peak_price=100.0)
        # Normal arm threshold = 0.15 + 0.02 = 0.17
        # risk_off regime lowers arm by 1%: effective = 0.16
        # 16.5% gain — above risk_off threshold (16%) but below normal (17%)
        current_price = 116.5

        # In risk_off: should arm (16.5% >= 16%)
        changed = update_position_state(pos, current_price, BALANCED, regime="risk_off")
        assert changed is True
        assert pos.exit_context is not None
        assert pos.exit_context["trailing_tp_armed"] is True

    def test_trailing_tp_not_armed_normal_regime_same_price(self) -> None:
        pos = _make_position(entry_price=100.0, peak_price=100.0)
        current_price = 116.5
        # In normal regime: 16.5% < 17% threshold → NOT armed
        changed = update_position_state(pos, current_price, BALANCED, regime="normal")
        exit_ctx = pos.exit_context or {}
        assert not exit_ctx.get("trailing_tp_armed", False)

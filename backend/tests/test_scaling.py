"""Tests for Position Scaling Up engine — pure function tests."""

from unittest.mock import MagicMock

from app.portfolio.scaling import (
    SCALE_UP_MAX,
    SCALE_UP_PROFIT_TRIGGER,
    SCALE_UP_SIZE_PCT,
    apply_scale_to_position,
    calculate_scale_buy,
    get_scale_state,
    should_scale_up,
)


# ── Helpers ──────────────────────────────────────────


def _make_position(
    entry_price: float = 100.0,
    quantity: float = 1.0,
    entry_value_usd: float = 100.0,
    stop_loss_price: float = 92.0,
    take_profit_price: float = 115.0,
    exit_context: dict | None = None,
) -> MagicMock:
    pos = MagicMock()
    pos.entry_price = entry_price
    pos.quantity = quantity
    pos.entry_value_usd = entry_value_usd
    pos.stop_loss_price = stop_loss_price
    pos.take_profit_price = take_profit_price
    pos.exit_context = exit_context
    return pos


def _make_profile(
    stop_loss_pct: float = -0.08,
    take_profit_pct: float = 0.15,
) -> MagicMock:
    profile = MagicMock()
    profile.stop_loss_pct = stop_loss_pct
    profile.take_profit_pct = take_profit_pct
    return profile


# ── get_scale_state ──────────────────────────────────


class TestGetScaleState:
    def test_default_when_exit_context_none(self) -> None:
        pos = _make_position(exit_context=None)
        state = get_scale_state(pos)

        assert state["scale_level"] == 0
        assert state["scale_ups"] == []
        assert state["original_entry"] == 100.0
        assert state["original_qty"] == 1.0

    def test_default_when_no_scale_key(self) -> None:
        pos = _make_position(exit_context={"dca": {"dca_level": 1}})
        state = get_scale_state(pos)

        assert state["scale_level"] == 0
        assert state["scale_ups"] == []

    def test_reads_existing_scale_data(self) -> None:
        scale_data = {
            "scale_level": 1,
            "scale_ups": [{"level": 1, "price": 110.0}],
            "original_entry": 100.0,
            "original_qty": 1.0,
        }
        pos = _make_position(exit_context={"scale": scale_data})
        state = get_scale_state(pos)

        assert state["scale_level"] == 1
        assert len(state["scale_ups"]) == 1
        assert state["original_entry"] == 100.0
        assert state["original_qty"] == 1.0


# ── should_scale_up ──────────────────────────────────


class TestShouldScaleUp:
    def test_triggers_when_profit_above_threshold(self) -> None:
        # 10% profit > 8% threshold
        assert should_scale_up(avg_entry=100.0, current_price=110.0, scale_level=0) is True

    def test_triggers_at_exact_threshold(self) -> None:
        # Exactly 8% profit
        assert should_scale_up(avg_entry=100.0, current_price=108.0, scale_level=0) is True

    def test_no_trigger_below_threshold(self) -> None:
        # 5% profit < 8% threshold
        assert should_scale_up(avg_entry=100.0, current_price=105.0, scale_level=0) is False

    def test_no_trigger_at_max_level(self) -> None:
        # Big profit but already scaled up
        assert should_scale_up(avg_entry=100.0, current_price=150.0, scale_level=SCALE_UP_MAX) is False

    def test_no_trigger_when_price_equals_entry(self) -> None:
        assert should_scale_up(avg_entry=100.0, current_price=100.0, scale_level=0) is False

    def test_no_trigger_when_price_below_entry(self) -> None:
        assert should_scale_up(avg_entry=100.0, current_price=90.0, scale_level=0) is False

    def test_custom_profit_trigger(self) -> None:
        # 5% custom threshold, 6% actual profit
        assert should_scale_up(
            avg_entry=100.0, current_price=106.0, scale_level=0, profit_trigger=0.05,
        ) is True
        # 10% custom threshold, 6% actual profit
        assert should_scale_up(
            avg_entry=100.0, current_price=106.0, scale_level=0, profit_trigger=0.10,
        ) is False

    def test_custom_max_levels(self) -> None:
        assert should_scale_up(
            avg_entry=100.0, current_price=120.0, scale_level=1, max_levels=1,
        ) is False
        assert should_scale_up(
            avg_entry=100.0, current_price=120.0, scale_level=1, max_levels=2,
        ) is True


# ── calculate_scale_buy ──────────────────────────────


class TestCalculateScaleBuy:
    def test_normal_buy(self) -> None:
        result = calculate_scale_buy(
            original_value=100.0, current_price=110.0,
            available_cash=500.0, min_position_usd=10.0,
        )
        assert result is not None
        # target = 100 * 0.50 = 50
        assert result["buy_value"] == 50.0
        assert abs(result["quantity"] - 50.0 / 110.0) < 1e-8
        assert result["price"] == 110.0

    def test_insufficient_cash(self) -> None:
        result = calculate_scale_buy(
            original_value=100.0, current_price=110.0,
            available_cash=5.0, min_position_usd=10.0,
        )
        assert result is None

    def test_cash_caps_buy_value(self) -> None:
        # Target = 100 * 0.5 = 50, but only 20 available
        result = calculate_scale_buy(
            original_value=100.0, current_price=110.0,
            available_cash=20.0, min_position_usd=10.0,
        )
        assert result is not None
        assert result["buy_value"] == 20.0
        assert abs(result["quantity"] - 20.0 / 110.0) < 1e-8

    def test_zero_available_cash(self) -> None:
        result = calculate_scale_buy(
            original_value=100.0, current_price=110.0,
            available_cash=0.0, min_position_usd=10.0,
        )
        assert result is None

    def test_custom_size_pct(self) -> None:
        result = calculate_scale_buy(
            original_value=200.0, current_price=110.0,
            available_cash=500.0, min_position_usd=10.0,
            size_pct=0.25,
        )
        assert result is not None
        # target = 200 * 0.25 = 50
        assert result["buy_value"] == 50.0

    def test_quantity_correct(self) -> None:
        result = calculate_scale_buy(
            original_value=1000.0, current_price=50.0,
            available_cash=5000.0, min_position_usd=10.0,
        )
        assert result is not None
        assert result["buy_value"] == 500.0
        assert abs(result["quantity"] - 10.0) < 1e-8


# ── apply_scale_to_position ──────────────────────────


class TestApplyScaleToPosition:
    def test_weighted_average_calculation(self) -> None:
        pos = _make_position(entry_price=100.0, quantity=1.0, entry_value_usd=100.0)
        profile = _make_profile()
        scale_buy = {"buy_value": 50.0, "quantity": 0.4545455, "price": 110.0}

        apply_scale_to_position(pos, scale_buy, profile)

        expected_avg = (100.0 * 1.0 + 110.0 * 0.4545455) / (1.0 + 0.4545455)
        assert abs(pos.entry_price - round(expected_avg, 8)) < 1e-6
        assert abs(pos.quantity - round(1.4545455, 8)) < 1e-6
        assert pos.entry_value_usd == 150.0

    def test_stop_loss_moves_to_break_even(self) -> None:
        pos = _make_position(
            entry_price=100.0, quantity=1.0, entry_value_usd=100.0,
            stop_loss_price=92.0,
        )
        profile = _make_profile(stop_loss_pct=-0.08)
        scale_buy = {"buy_value": 50.0, "quantity": 0.4545455, "price": 110.0}

        apply_scale_to_position(pos, scale_buy, profile)

        # Stop loss should be at original entry (break-even), not profile-based
        assert pos.stop_loss_price == 100.0

    def test_take_profit_recalculated(self) -> None:
        pos = _make_position(entry_price=100.0, quantity=1.0, entry_value_usd=100.0)
        profile = _make_profile(take_profit_pct=0.15)
        scale_buy = {"buy_value": 50.0, "quantity": 0.4545455, "price": 110.0}

        apply_scale_to_position(pos, scale_buy, profile)

        new_avg = (100.0 * 1.0 + 110.0 * 0.4545455) / (1.0 + 0.4545455)
        expected_tp = round(new_avg * (1 + 0.15), 8)
        assert pos.take_profit_price == expected_tp

    def test_scale_state_stored_in_exit_context(self) -> None:
        pos = _make_position(
            entry_price=100.0, quantity=1.0, entry_value_usd=100.0,
            exit_context={"dca": {"dca_level": 0}},
        )
        profile = _make_profile()
        scale_buy = {"buy_value": 50.0, "quantity": 0.4545455, "price": 110.0}

        state = apply_scale_to_position(pos, scale_buy, profile)

        assert state["scale_level"] == 1
        assert len(state["scale_ups"]) == 1
        assert state["scale_ups"][0]["level"] == 1
        assert state["scale_ups"][0]["price"] == 110.0
        # Verify existing exit_context keys preserved
        assert "dca" in pos.exit_context
        assert "scale" in pos.exit_context

    def test_scale_state_when_no_prior_context(self) -> None:
        pos = _make_position(
            entry_price=100.0, quantity=1.0, entry_value_usd=100.0,
            exit_context=None,
        )
        profile = _make_profile()
        scale_buy = {"buy_value": 50.0, "quantity": 0.4545455, "price": 110.0}

        state = apply_scale_to_position(pos, scale_buy, profile)

        assert state["scale_level"] == 1
        assert pos.exit_context["scale"]["scale_level"] == 1

    def test_original_entry_preserved_in_state(self) -> None:
        pos = _make_position(entry_price=100.0, quantity=1.0, entry_value_usd=100.0)
        profile = _make_profile()
        scale_buy = {"buy_value": 50.0, "quantity": 0.4545455, "price": 110.0}

        state = apply_scale_to_position(pos, scale_buy, profile)

        assert state["original_entry"] == 100.0
        assert state["original_qty"] == 1.0


# ── Edge cases ───────────────────────────────────────


class TestEdgeCases:
    def test_already_at_max_scale_ups(self) -> None:
        """should_scale_up returns False when already at max."""
        assert should_scale_up(avg_entry=100.0, current_price=120.0, scale_level=1) is False

    def test_zero_cash_returns_none(self) -> None:
        result = calculate_scale_buy(
            original_value=100.0, current_price=110.0,
            available_cash=0.0, min_position_usd=10.0,
        )
        assert result is None

    def test_constants_have_expected_values(self) -> None:
        assert SCALE_UP_MAX == 1
        assert SCALE_UP_PROFIT_TRIGGER == 0.08
        assert SCALE_UP_SIZE_PCT == 0.50

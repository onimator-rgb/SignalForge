"""Tests for DCA (Dollar Cost Averaging) engine — pure function tests."""

from unittest.mock import MagicMock

import pytest

from app.portfolio.dca import (
    DCA_DROP_PCT,
    DCA_LEVEL_MULTIPLIERS,
    DCA_MAX_LEVELS,
    DCAConfig,
    apply_dca_to_position,
    calculate_dca_buy,
    compute_dca_order,
    compute_new_avg_price,
    get_dca_state,
    should_dca,
    should_dca_pure,
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


# ════════════════════════════════════════════════════════
# Pure-logic layer tests
# ════════════════════════════════════════════════════════


class TestDCAConfig:
    def test_valid_defaults(self) -> None:
        cfg = DCAConfig()
        assert cfg.max_levels == 3
        assert cfg.drop_trigger_pct == [5.0, 10.0, 20.0]
        assert cfg.tranche_pcts == [0.3, 0.4, 0.3]

    def test_custom_config(self) -> None:
        cfg = DCAConfig(
            max_levels=2,
            drop_trigger_pct=[3.0, 8.0],
            tranche_pcts=[0.6, 0.4],
        )
        assert cfg.max_levels == 2
        assert cfg.drop_trigger_pct == [3.0, 8.0]
        assert cfg.tranche_pcts == [0.6, 0.4]

    def test_frozen(self) -> None:
        cfg = DCAConfig()
        with pytest.raises(AttributeError):
            cfg.max_levels = 5  # type: ignore[misc]

    def test_mismatched_drop_trigger_length(self) -> None:
        with pytest.raises(ValueError, match="drop_trigger_pct length"):
            DCAConfig(max_levels=2, drop_trigger_pct=[5.0, 10.0, 20.0])

    def test_mismatched_tranche_length(self) -> None:
        with pytest.raises(ValueError, match="tranche_pcts length"):
            DCAConfig(max_levels=3, tranche_pcts=[0.5, 0.5])

    def test_non_increasing_triggers(self) -> None:
        with pytest.raises(ValueError, match="strictly increasing"):
            DCAConfig(
                max_levels=3,
                drop_trigger_pct=[5.0, 5.0, 20.0],
            )

    def test_decreasing_triggers(self) -> None:
        with pytest.raises(ValueError, match="strictly increasing"):
            DCAConfig(
                max_levels=3,
                drop_trigger_pct=[10.0, 5.0, 20.0],
            )

    def test_negative_trigger(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            DCAConfig(
                max_levels=3,
                drop_trigger_pct=[-1.0, 5.0, 10.0],
            )

    def test_tranche_pcts_not_summing_to_one(self) -> None:
        with pytest.raises(ValueError, match="sum to ~1.0"):
            DCAConfig(
                max_levels=3,
                drop_trigger_pct=[5.0, 10.0, 20.0],
                tranche_pcts=[0.3, 0.3, 0.3],
            )


class TestShouldDcaPure:
    def test_triggers_at_exact_threshold(self) -> None:
        cfg = DCAConfig()
        # 5% drop from 100 -> price = 95
        assert should_dca_pure(95.0, 100.0, 0, cfg) is True

    def test_no_trigger_above_threshold(self) -> None:
        cfg = DCAConfig()
        # 4.99% drop -> should not trigger level 0 (requires 5%)
        assert should_dca_pure(95.01, 100.0, 0, cfg) is False

    def test_triggers_deeper_drop(self) -> None:
        cfg = DCAConfig()
        # 15% drop, level 1 requires 10% -> triggers
        assert should_dca_pure(85.0, 100.0, 1, cfg) is True

    def test_all_levels_exhausted(self) -> None:
        cfg = DCAConfig()
        assert should_dca_pure(50.0, 100.0, 3, cfg) is False

    def test_price_above_entry(self) -> None:
        cfg = DCAConfig()
        assert should_dca_pure(105.0, 100.0, 0, cfg) is False

    def test_price_equal_entry(self) -> None:
        cfg = DCAConfig()
        assert should_dca_pure(100.0, 100.0, 0, cfg) is False

    def test_second_level_exact(self) -> None:
        cfg = DCAConfig()
        # Level 1 requires 10% drop -> price = 90
        assert should_dca_pure(90.0, 100.0, 1, cfg) is True

    def test_third_level_exact(self) -> None:
        cfg = DCAConfig()
        # Level 2 requires 20% drop -> price = 80
        assert should_dca_pure(80.0, 100.0, 2, cfg) is True
        assert should_dca_pure(80.01, 100.0, 2, cfg) is False


class TestComputeDCAOrder:
    def test_first_level(self) -> None:
        cfg = DCAConfig()
        result = compute_dca_order(1000.0, 0, cfg)
        assert result == pytest.approx(300.0)  # 1000 * 0.3

    def test_second_level(self) -> None:
        cfg = DCAConfig()
        result = compute_dca_order(700.0, 1, cfg)
        assert result == pytest.approx(280.0)  # 700 * 0.4

    def test_third_level(self) -> None:
        cfg = DCAConfig()
        result = compute_dca_order(420.0, 2, cfg)
        assert result == pytest.approx(126.0)  # 420 * 0.3

    def test_zero_remaining_capital(self) -> None:
        cfg = DCAConfig()
        assert compute_dca_order(0.0, 0, cfg) == 0.0

    def test_negative_remaining_capital(self) -> None:
        cfg = DCAConfig()
        assert compute_dca_order(-100.0, 0, cfg) == 0.0

    def test_exhausted_levels_raises(self) -> None:
        cfg = DCAConfig()
        with pytest.raises(ValueError, match="DCA levels already used"):
            compute_dca_order(1000.0, 3, cfg)

    def test_over_exhausted_raises(self) -> None:
        cfg = DCAConfig()
        with pytest.raises(ValueError):
            compute_dca_order(1000.0, 5, cfg)


class TestComputeNewAvgPrice:
    def test_basic_weighted_average(self) -> None:
        # 10 shares @ $100, buy 5 more @ $80
        result = compute_new_avg_price(100.0, 10.0, 80.0, 5.0)
        expected = (100.0 * 10.0 + 80.0 * 5.0) / 15.0  # 93.333...
        assert result == pytest.approx(expected)

    def test_equal_quantities(self) -> None:
        result = compute_new_avg_price(100.0, 1.0, 80.0, 1.0)
        assert result == pytest.approx(90.0)

    def test_zero_total_quantity_raises(self) -> None:
        with pytest.raises(ValueError, match="zero"):
            compute_new_avg_price(100.0, 0.0, 80.0, 0.0)

    def test_small_fractional_quantities(self) -> None:
        result = compute_new_avg_price(50000.0, 0.001, 48000.0, 0.002)
        expected = (50000.0 * 0.001 + 48000.0 * 0.002) / 0.003
        assert result == pytest.approx(expected)


# ════════════════════════════════════════════════════════
# Position-aware layer tests (original)
# ════════════════════════════════════════════════════════


class TestGetDcaState:
    def test_default_when_exit_context_none(self) -> None:
        pos = _make_position(exit_context=None)
        state = get_dca_state(pos)

        assert state["dca_level"] == 0
        assert state["dca_buys"] == []
        assert state["original_entry"] == 100.0
        assert state["original_qty"] == 1.0

    def test_default_when_no_dca_key(self) -> None:
        pos = _make_position(exit_context={"entry_slippage": {}})
        state = get_dca_state(pos)

        assert state["dca_level"] == 0
        assert state["dca_buys"] == []

    def test_reads_existing_dca_data(self) -> None:
        dca_data = {
            "dca_level": 2,
            "dca_buys": [{"level": 1}, {"level": 2}],
            "original_entry": 105.0,
            "original_qty": 0.5,
        }
        pos = _make_position(exit_context={"dca": dca_data})
        state = get_dca_state(pos)

        assert state["dca_level"] == 2
        assert len(state["dca_buys"]) == 2
        assert state["original_entry"] == 105.0
        assert state["original_qty"] == 0.5


class TestShouldDca:
    def test_first_level_triggers(self) -> None:
        assert should_dca(avg_entry=100.0, current_price=94.0, dca_level=0) is True

    def test_first_level_exact_threshold(self) -> None:
        assert should_dca(avg_entry=100.0, current_price=95.0, dca_level=0) is True

    def test_second_level_triggers(self) -> None:
        assert should_dca(avg_entry=100.0, current_price=89.0, dca_level=1) is True

    def test_third_level_triggers(self) -> None:
        assert should_dca(avg_entry=100.0, current_price=84.0, dca_level=2) is True

    def test_max_level_reached(self) -> None:
        assert should_dca(avg_entry=100.0, current_price=50.0, dca_level=DCA_MAX_LEVELS) is False

    def test_price_not_low_enough(self) -> None:
        assert should_dca(avg_entry=100.0, current_price=96.0, dca_level=0) is False

    def test_custom_drop_pct(self) -> None:
        assert should_dca(avg_entry=100.0, current_price=89.0, dca_level=0, drop_pct=-0.10) is True
        assert should_dca(avg_entry=100.0, current_price=91.0, dca_level=0, drop_pct=-0.10) is False

    def test_custom_max_levels(self) -> None:
        assert should_dca(avg_entry=100.0, current_price=50.0, dca_level=1, max_levels=1) is False
        assert should_dca(avg_entry=100.0, current_price=50.0, dca_level=1, max_levels=2) is True


class TestCalculateDcaBuy:
    def test_normal_buy(self) -> None:
        result = calculate_dca_buy(
            original_value=100.0, dca_level=0,
            current_price=95.0, available_cash=500.0,
            min_position_usd=10.0,
        )
        assert result is not None
        assert result["buy_value"] == 50.0
        assert abs(result["quantity"] - 50.0 / 95.0) < 1e-8
        assert result["price"] == 95.0

    def test_insufficient_cash(self) -> None:
        result = calculate_dca_buy(
            original_value=100.0, dca_level=0,
            current_price=95.0, available_cash=5.0,
            min_position_usd=10.0,
        )
        assert result is None

    def test_cash_limits_buy_value(self) -> None:
        result = calculate_dca_buy(
            original_value=100.0, dca_level=0,
            current_price=95.0, available_cash=20.0,
            min_position_usd=10.0,
        )
        assert result is not None
        assert result["buy_value"] == 20.0

    def test_level_multiplier_scaling(self) -> None:
        for level, mult in enumerate(DCA_LEVEL_MULTIPLIERS):
            result = calculate_dca_buy(
                original_value=200.0, dca_level=level,
                current_price=90.0, available_cash=1000.0,
                min_position_usd=10.0,
            )
            assert result is not None
            expected_value = 200.0 * mult
            assert result["buy_value"] == expected_value

    def test_level_beyond_multipliers(self) -> None:
        result = calculate_dca_buy(
            original_value=100.0, dca_level=len(DCA_LEVEL_MULTIPLIERS),
            current_price=90.0, available_cash=1000.0,
            min_position_usd=10.0,
        )
        assert result is None


class TestApplyDcaToPosition:
    def test_weighted_average_calculation(self) -> None:
        pos = _make_position(entry_price=100.0, quantity=1.0, entry_value_usd=100.0)
        profile = _make_profile()
        dca_buy = {"buy_value": 50.0, "quantity": 0.5555556, "price": 90.0}

        apply_dca_to_position(pos, dca_buy, profile)

        expected_avg = (100.0 * 1.0 + 90.0 * 0.5555556) / (1.0 + 0.5555556)
        assert abs(pos.entry_price - round(expected_avg, 8)) < 1e-6
        assert abs(pos.quantity - round(1.5555556, 8)) < 1e-6
        assert pos.entry_value_usd == 150.0

    def test_stop_loss_recalculated(self) -> None:
        pos = _make_position(entry_price=100.0, quantity=1.0, entry_value_usd=100.0)
        profile = _make_profile(stop_loss_pct=-0.08)
        dca_buy = {"buy_value": 50.0, "quantity": 0.5, "price": 90.0}

        apply_dca_to_position(pos, dca_buy, profile)

        new_avg = (100.0 * 1.0 + 90.0 * 0.5) / 1.5
        expected_sl = round(new_avg * (1 + (-0.08)), 8)
        assert pos.stop_loss_price == expected_sl

    def test_take_profit_recalculated(self) -> None:
        pos = _make_position(entry_price=100.0, quantity=1.0, entry_value_usd=100.0)
        profile = _make_profile(take_profit_pct=0.15)
        dca_buy = {"buy_value": 50.0, "quantity": 0.5, "price": 90.0}

        apply_dca_to_position(pos, dca_buy, profile)

        new_avg = (100.0 * 1.0 + 90.0 * 0.5) / 1.5
        expected_tp = round(new_avg * (1 + 0.15), 8)
        assert pos.take_profit_price == expected_tp

    def test_dca_state_updated_in_exit_context(self) -> None:
        pos = _make_position(
            entry_price=100.0, quantity=1.0, entry_value_usd=100.0,
            exit_context={"entry_slippage": {"market_price": 100.0}},
        )
        profile = _make_profile()
        dca_buy = {"buy_value": 50.0, "quantity": 0.5, "price": 90.0}

        state = apply_dca_to_position(pos, dca_buy, profile)

        assert state["dca_level"] == 1
        assert len(state["dca_buys"]) == 1
        assert state["dca_buys"][0]["level"] == 1
        assert state["dca_buys"][0]["price"] == 90.0
        assert "entry_slippage" in pos.exit_context
        assert "dca" in pos.exit_context

    def test_dca_state_when_no_prior_context(self) -> None:
        pos = _make_position(
            entry_price=100.0, quantity=1.0, entry_value_usd=100.0,
            exit_context=None,
        )
        profile = _make_profile()
        dca_buy = {"buy_value": 50.0, "quantity": 0.5, "price": 90.0}

        state = apply_dca_to_position(pos, dca_buy, profile)

        assert state["dca_level"] == 1
        assert pos.exit_context["dca"]["dca_level"] == 1

    def test_second_dca_buy_increments_level(self) -> None:
        pos = _make_position(
            entry_price=96.42857143, quantity=1.5, entry_value_usd=150.0,
            exit_context={
                "dca": {
                    "dca_level": 1,
                    "dca_buys": [{"level": 1, "price": 90.0, "quantity": 0.5, "value": 50.0, "new_avg_entry": 96.42857143}],
                    "original_entry": 100.0,
                    "original_qty": 1.0,
                }
            },
        )
        profile = _make_profile()
        dca_buy = {"buy_value": 75.0, "quantity": 0.9375, "price": 80.0}

        state = apply_dca_to_position(pos, dca_buy, profile)

        assert state["dca_level"] == 2
        assert len(state["dca_buys"]) == 2
        expected_avg = (96.42857143 * 1.5 + 80.0 * 0.9375) / (1.5 + 0.9375)
        assert abs(pos.entry_price - round(expected_avg, 8)) < 1e-4

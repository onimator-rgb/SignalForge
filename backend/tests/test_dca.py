"""Tests for DCA (Dollar Cost Averaging) engine — pure function tests."""

from unittest.mock import MagicMock

from app.portfolio.dca import (
    DCA_DROP_PCT,
    DCA_LEVEL_MULTIPLIERS,
    DCA_MAX_LEVELS,
    apply_dca_to_position,
    calculate_dca_buy,
    get_dca_state,
    should_dca,
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


# ── get_dca_state ────────────────────────────────────


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


# ── should_dca ───────────────────────────────────────


class TestShouldDca:
    def test_first_level_triggers(self) -> None:
        # Level 0: threshold = 100 * (1 + (-0.05) * 1) = 95.0
        assert should_dca(avg_entry=100.0, current_price=94.0, dca_level=0) is True

    def test_first_level_exact_threshold(self) -> None:
        assert should_dca(avg_entry=100.0, current_price=95.0, dca_level=0) is True

    def test_second_level_triggers(self) -> None:
        # Level 1: threshold = 100 * (1 + (-0.05) * 2) = 90.0
        assert should_dca(avg_entry=100.0, current_price=89.0, dca_level=1) is True

    def test_third_level_triggers(self) -> None:
        # Level 2: threshold = 100 * (1 + (-0.05) * 3) = 85.0
        assert should_dca(avg_entry=100.0, current_price=84.0, dca_level=2) is True

    def test_max_level_reached(self) -> None:
        assert should_dca(avg_entry=100.0, current_price=50.0, dca_level=DCA_MAX_LEVELS) is False

    def test_price_not_low_enough(self) -> None:
        # Level 0: threshold = 95.0, price = 96 -> no DCA
        assert should_dca(avg_entry=100.0, current_price=96.0, dca_level=0) is False

    def test_custom_drop_pct(self) -> None:
        # Custom 10% drop: threshold = 100 * (1 + (-0.10) * 1) = 90.0
        assert should_dca(avg_entry=100.0, current_price=89.0, dca_level=0, drop_pct=-0.10) is True
        assert should_dca(avg_entry=100.0, current_price=91.0, dca_level=0, drop_pct=-0.10) is False

    def test_custom_max_levels(self) -> None:
        assert should_dca(avg_entry=100.0, current_price=50.0, dca_level=1, max_levels=1) is False
        assert should_dca(avg_entry=100.0, current_price=50.0, dca_level=1, max_levels=2) is True


# ── calculate_dca_buy ────────────────────────────────


class TestCalculateDcaBuy:
    def test_normal_buy(self) -> None:
        result = calculate_dca_buy(
            original_value=100.0, dca_level=0,
            current_price=95.0, available_cash=500.0,
            min_position_usd=10.0,
        )
        assert result is not None
        # Level 0 multiplier = 0.5, target = 100 * 0.5 = 50
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
        # Target = 100 * 0.5 = 50, but only 20 available
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


# ── apply_dca_to_position ────────────────────────────


class TestApplyDcaToPosition:
    def test_weighted_average_calculation(self) -> None:
        pos = _make_position(entry_price=100.0, quantity=1.0, entry_value_usd=100.0)
        profile = _make_profile()
        dca_buy = {"buy_value": 50.0, "quantity": 0.5555556, "price": 90.0}

        apply_dca_to_position(pos, dca_buy, profile)

        # new_avg = (100*1 + 90*0.5555556) / (1 + 0.5555556) = 150 / 1.5555556 ≈ 96.428...
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
        # Verify exit_context preserved existing keys
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
        # Verify weighted average: (96.43*1.5 + 80*0.9375) / (1.5 + 0.9375)
        expected_avg = (96.42857143 * 1.5 + 80.0 * 0.9375) / (1.5 + 0.9375)
        assert abs(pos.entry_price - round(expected_avg, 8)) < 1e-4

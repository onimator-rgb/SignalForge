"""Tests for the grid bot preset – generate_grid_rules()."""

from __future__ import annotations

import pytest

from app.strategies.presets.grid import generate_grid_rules


class TestBasicGridGeneration:
    """test_basic_grid_generation: 4 grids between 100-200."""

    def test_basic_grid_generation(self) -> None:
        rules = generate_grid_rules(100, 200, 4, 10.0)
        # 4 grids -> 5 levels: 100, 125, 150, 175, 200
        # midpoint = 150
        # buy: 100, 125, 150 (<=150)  sell: 175, 200 (>150)
        buy_rules = [r for r in rules if r["action"] == "buy"]
        sell_rules = [r for r in rules if r["action"] == "sell"]
        assert len(buy_rules) == 3
        assert len(sell_rules) == 2
        assert len(rules) == 5


class TestGridSpacing:
    """test_grid_spacing_uniform: verify all grid levels are evenly spaced."""

    def test_grid_spacing_uniform(self) -> None:
        rules = generate_grid_rules(100, 200, 4, 10.0)
        prices = [r["conditions"][0]["value"] for r in rules]
        spacings = [prices[i + 1] - prices[i] for i in range(len(prices) - 1)]
        for s in spacings:
            assert abs(s - 25.0) < 1e-9


class TestBuyRulesBelowMidpoint:
    def test_buy_rules_below_midpoint(self) -> None:
        rules = generate_grid_rules(100, 200, 4, 10.0)
        midpoint = 150.0
        for r in rules:
            if r["action"] == "buy":
                assert r["conditions"][0]["value"] <= midpoint


class TestSellRulesAboveMidpoint:
    def test_sell_rules_above_midpoint(self) -> None:
        rules = generate_grid_rules(100, 200, 4, 10.0)
        midpoint = 150.0
        for r in rules:
            if r["action"] == "sell":
                assert r["conditions"][0]["value"] >= midpoint


class TestAmountPerGrid:
    def test_amount_per_grid(self) -> None:
        rules = generate_grid_rules(100, 200, 4, 42.5)
        for r in rules:
            assert r["amount"] == 42.5


class TestRulesSortedByPrice:
    def test_rules_sorted_by_price(self) -> None:
        rules = generate_grid_rules(100, 200, 10, 5.0)
        prices = [r["conditions"][0]["value"] for r in rules]
        assert prices == sorted(prices)


class TestInvalidInputs:
    def test_invalid_lower_gte_upper(self) -> None:
        with pytest.raises(ValueError, match="upper_price must be greater"):
            generate_grid_rules(200, 100, 4, 10.0)

    def test_invalid_num_grids_lt_2(self) -> None:
        with pytest.raises(ValueError, match="num_grids must be at least 2"):
            generate_grid_rules(100, 200, 1, 10.0)

    def test_invalid_negative_price(self) -> None:
        with pytest.raises(ValueError, match="lower_price must be positive"):
            generate_grid_rules(-10, 200, 4, 10.0)

    def test_invalid_zero_amount(self) -> None:
        with pytest.raises(ValueError, match="amount_per_grid must be positive"):
            generate_grid_rules(100, 200, 4, 0)


class TestManyGrids:
    def test_many_grids(self) -> None:
        rules = generate_grid_rules(50, 150, 20, 1.0)
        assert len(rules) == 21
        prices = [r["conditions"][0]["value"] for r in rules]
        assert len(set(prices)) == len(prices), "No duplicate levels"


class TestRuleDictStructure:
    def test_rule_dict_structure(self) -> None:
        rules = generate_grid_rules(100, 200, 4, 10.0)
        required_keys = {"conditions", "action", "weight", "description", "amount"}
        for r in rules:
            assert required_keys.issubset(r.keys())
            assert isinstance(r["conditions"], list)
            assert len(r["conditions"]) >= 1
            cond = r["conditions"][0]
            assert "indicator" in cond
            assert "operator" in cond
            assert "value" in cond
            assert r["action"] in ("buy", "sell")
            assert r["weight"] == 1.0

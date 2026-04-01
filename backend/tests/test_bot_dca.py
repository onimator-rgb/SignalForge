"""Tests for DCA (Dollar-Cost Averaging) bot preset."""

import pytest

from app.strategies.presets.dca_bot import generate_dca_rules


class TestBasicDcaGeneration:
    def test_two_rules_without_bonus(self) -> None:
        rules = generate_dca_rules(interval_hours=24, amount_per_buy=50.0, max_buys=10)
        assert len(rules) == 2

    def test_three_rules_with_bonus(self) -> None:
        rules = generate_dca_rules(
            interval_hours=24, amount_per_buy=50.0, max_buys=10, price_drop_bonus_pct=5.0,
        )
        assert len(rules) == 3


class TestBaseRuleStructure:
    def test_base_rule_structure(self) -> None:
        rules = generate_dca_rules(interval_hours=24, amount_per_buy=50.0, max_buys=10)
        base_rule = [r for r in rules if r["action"] == "buy"][0]
        assert len(base_rule["conditions"]) == 1
        cond = base_rule["conditions"][0]
        assert cond["indicator"] == "hours_since_last_buy"
        assert cond["operator"] == "gte"
        assert cond["value"] == 24
        assert base_rule["weight"] == 1.0
        assert base_rule["amount"] == 50.0


class TestMaxBuysGuard:
    def test_max_buys_guard(self) -> None:
        rules = generate_dca_rules(interval_hours=24, amount_per_buy=50.0, max_buys=10)
        guard = [r for r in rules if r["action"] == "hold"][0]
        assert guard["weight"] == 10.0
        assert guard["amount"] == 0
        cond = guard["conditions"][0]
        assert cond["indicator"] == "total_buys"
        assert cond["operator"] == "gte"
        assert cond["value"] == 10


class TestBonusBuyRule:
    def test_bonus_buy_has_double_amount(self) -> None:
        rules = generate_dca_rules(
            interval_hours=24, amount_per_buy=50.0, max_buys=10, price_drop_bonus_pct=5.0,
        )
        bonus = [r for r in rules if r["weight"] == 2.0][0]
        assert bonus["amount"] == 100.0
        assert bonus["action"] == "buy"

    def test_bonus_buy_has_two_conditions(self) -> None:
        rules = generate_dca_rules(
            interval_hours=24, amount_per_buy=50.0, max_buys=10, price_drop_bonus_pct=5.0,
        )
        bonus = [r for r in rules if r["weight"] == 2.0][0]
        assert len(bonus["conditions"]) == 2
        indicators = {c["indicator"] for c in bonus["conditions"]}
        assert indicators == {"hours_since_last_buy", "price_change_pct"}


class TestZeroBonusOmitsBonusRule:
    def test_zero_bonus_omits_bonus_rule(self) -> None:
        rules = generate_dca_rules(interval_hours=24, amount_per_buy=50.0, max_buys=10)
        assert len(rules) == 2
        assert all(r["weight"] != 2.0 for r in rules)


class TestRuleDictKeys:
    def test_rule_dict_keys(self) -> None:
        rules = generate_dca_rules(
            interval_hours=24, amount_per_buy=50.0, max_buys=10, price_drop_bonus_pct=5.0,
        )
        required_keys = {"conditions", "action", "weight", "description", "amount"}
        for rule in rules:
            assert set(rule.keys()) == required_keys


class TestValidation:
    def test_invalid_interval_hours_zero(self) -> None:
        with pytest.raises(ValueError, match="interval_hours must be greater than 0"):
            generate_dca_rules(interval_hours=0, amount_per_buy=50.0, max_buys=10)

    def test_invalid_interval_hours_negative(self) -> None:
        with pytest.raises(ValueError, match="interval_hours must be greater than 0"):
            generate_dca_rules(interval_hours=-1, amount_per_buy=50.0, max_buys=10)

    def test_invalid_amount_zero(self) -> None:
        with pytest.raises(ValueError, match="amount_per_buy must be greater than 0"):
            generate_dca_rules(interval_hours=24, amount_per_buy=0, max_buys=10)

    def test_invalid_amount_negative(self) -> None:
        with pytest.raises(ValueError, match="amount_per_buy must be greater than 0"):
            generate_dca_rules(interval_hours=24, amount_per_buy=-10.0, max_buys=10)

    def test_invalid_max_buys_zero(self) -> None:
        with pytest.raises(ValueError, match="max_buys must be >= 1"):
            generate_dca_rules(interval_hours=24, amount_per_buy=50.0, max_buys=0)

    def test_invalid_bonus_pct_negative(self) -> None:
        with pytest.raises(ValueError, match="price_drop_bonus_pct must be >= 0"):
            generate_dca_rules(
                interval_hours=24, amount_per_buy=50.0, max_buys=10, price_drop_bonus_pct=-1.0,
            )

    def test_invalid_bonus_pct_gte_100(self) -> None:
        with pytest.raises(ValueError, match="price_drop_bonus_pct must be less than 100"):
            generate_dca_rules(
                interval_hours=24, amount_per_buy=50.0, max_buys=10, price_drop_bonus_pct=100.0,
            )


class TestSorting:
    def test_rules_sorted_by_weight(self) -> None:
        rules = generate_dca_rules(
            interval_hours=24, amount_per_buy=50.0, max_buys=10, price_drop_bonus_pct=5.0,
        )
        weights = [r["weight"] for r in rules]
        assert weights == sorted(weights)

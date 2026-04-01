"""Tests for BTD (Buy The Dip) bot preset."""

import pytest

from app.strategies.presets.btd import generate_btd_rules


class TestBasicBtdGeneration:
    def test_basic_btd_generation(self) -> None:
        rules = generate_btd_rules(dip_pct=5.0, recovery_pct=2.0, take_profit_pct=10.0)
        assert len(rules) == 3
        actions = [r["action"] for r in rules]
        assert actions.count("buy") == 2
        assert actions.count("sell") == 1


class TestDipRuleStructure:
    def test_dip_rule_structure(self) -> None:
        rules = generate_btd_rules(dip_pct=5.0, recovery_pct=2.0, take_profit_pct=10.0)
        dip_rule = [r for r in rules if r["weight"] == 1.0 and r["action"] == "buy"][0]
        assert len(dip_rule["conditions"]) == 1
        cond = dip_rule["conditions"][0]
        assert cond["indicator"] == "price_change_pct"
        assert cond["operator"] == "lte"
        assert cond["value"] == -5.0


class TestRecoveryRule:
    def test_recovery_rule_has_two_conditions(self) -> None:
        rules = generate_btd_rules(dip_pct=5.0, recovery_pct=2.0, take_profit_pct=10.0)
        recovery_rule = [r for r in rules if r["weight"] == 2.0][0]
        assert len(recovery_rule["conditions"]) == 2
        indicators = {c["indicator"] for c in recovery_rule["conditions"]}
        assert indicators == {"price_change_pct", "price_recovery_pct"}


class TestTakeProfitRule:
    def test_take_profit_rule(self) -> None:
        rules = generate_btd_rules(dip_pct=5.0, recovery_pct=2.0, take_profit_pct=10.0)
        tp_rule = [r for r in rules if r["action"] == "sell"][0]
        assert len(tp_rule["conditions"]) == 1
        cond = tp_rule["conditions"][0]
        assert cond["indicator"] == "position_gain_pct"
        assert cond["operator"] == "gte"
        assert cond["value"] == 10.0


class TestZeroRecovery:
    def test_zero_recovery_omits_confirmation(self) -> None:
        rules = generate_btd_rules(dip_pct=5.0, recovery_pct=0, take_profit_pct=10.0)
        assert len(rules) == 2
        assert all(r["weight"] != 2.0 for r in rules)


class TestRuleDictKeys:
    def test_rule_dict_keys(self) -> None:
        rules = generate_btd_rules(dip_pct=5.0, recovery_pct=2.0, take_profit_pct=10.0)
        required_keys = {"conditions", "action", "weight", "description", "amount"}
        for rule in rules:
            assert set(rule.keys()) == required_keys


class TestValidation:
    def test_invalid_dip_pct_zero(self) -> None:
        with pytest.raises(ValueError, match="dip_pct must be greater than 0"):
            generate_btd_rules(dip_pct=0, recovery_pct=2.0, take_profit_pct=10.0)

    def test_invalid_dip_pct_gte_100(self) -> None:
        with pytest.raises(ValueError, match="dip_pct must be less than 100"):
            generate_btd_rules(dip_pct=100, recovery_pct=2.0, take_profit_pct=10.0)

    def test_invalid_negative_take_profit(self) -> None:
        with pytest.raises(ValueError, match="take_profit_pct must be greater than 0"):
            generate_btd_rules(dip_pct=5.0, recovery_pct=2.0, take_profit_pct=-1.0)


class TestSorting:
    def test_rules_sorted_by_weight(self) -> None:
        rules = generate_btd_rules(dip_pct=5.0, recovery_pct=2.0, take_profit_pct=10.0)
        weights = [r["weight"] for r in rules]
        assert weights == sorted(weights)

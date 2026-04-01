"""Tests for strategy rule data model and in-memory store."""

import pytest
from pydantic import ValidationError

from app.strategies.models import (
    Strategy,
    StrategyAction,
    StrategyCondition,
    StrategyRule,
    StrategyStore,
)


def _make_rule(
    indicator: str = "rsi",
    operator: str = "gt",
    value: float = 70.0,
    action: str = "sell",
    **cond_kw: object,
) -> StrategyRule:
    return StrategyRule(
        condition=StrategyCondition(indicator=indicator, operator=operator, value=value, **cond_kw),  # type: ignore[arg-type]
        action=StrategyAction(action=action),  # type: ignore[arg-type]
    )


def _make_strategy(**kw: object) -> Strategy:
    defaults: dict[str, object] = {"name": "Test Strategy", "rules": [_make_rule()]}
    defaults.update(kw)
    return Strategy(**defaults)  # type: ignore[arg-type]


# ── Model validation ──────────────────────────────────────────────────────


def test_valid_rule_creation() -> None:
    rule = _make_rule(indicator="rsi", operator="gt", value=70.0, action="sell")
    assert rule.condition.indicator == "rsi"
    assert rule.condition.operator == "gt"
    assert rule.condition.value == 70.0
    assert rule.action.action == "sell"


def test_between_operator_requires_upper() -> None:
    with pytest.raises(ValidationError, match="value_upper"):
        _make_rule(operator="between", value=30.0)


def test_between_operator_with_upper() -> None:
    rule = _make_rule(operator="between", value=30.0, value_upper=70.0)
    assert rule.condition.value_upper == 70.0


def test_strategy_requires_at_least_one_rule() -> None:
    with pytest.raises(ValidationError):
        Strategy(name="Empty", rules=[])


def test_strategy_name_limits() -> None:
    with pytest.raises(ValidationError):
        Strategy(name="", rules=[_make_rule()])

    long_name = "x" * 100
    s = Strategy(name=long_name, rules=[_make_rule()])
    assert s.name == long_name


def test_strategy_signal_actions_property() -> None:
    rules = [
        _make_rule(action="buy"),
        _make_rule(action="sell"),
        _make_rule(action="buy"),
    ]
    s = Strategy(name="Multi", rules=rules)
    assert s.signal_actions == {"buy", "sell"}


# ── Store CRUD ─────────────────────────────────────────────────────────────


def test_store_add_and_get() -> None:
    store = StrategyStore()
    s = _make_strategy()
    store.add(s)
    assert store.get(s.id) is s


def test_store_list_all() -> None:
    store = StrategyStore()
    s1 = _make_strategy(name="A")
    s2 = _make_strategy(name="B")
    store.add(s1)
    store.add(s2)
    assert len(store.list_all()) == 2


def test_store_delete() -> None:
    store = StrategyStore()
    s = _make_strategy()
    store.add(s)
    assert store.delete(s.id) is True
    assert store.get(s.id) is None


def test_store_delete_nonexistent() -> None:
    store = StrategyStore()
    assert store.delete("nonexistent") is False


def test_strategy_default_values() -> None:
    s = _make_strategy()
    assert len(s.id) == 32  # uuid4().hex
    assert s.created_at is not None
    assert s.profile_name == "balanced"
    assert s.is_preset is False

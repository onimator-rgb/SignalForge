"""BTD (Buy The Dip) Bot preset – generate buy/sell rules for dip-buying strategy."""

from __future__ import annotations


def generate_btd_rules(
    dip_pct: float,
    recovery_pct: float,
    take_profit_pct: float,
) -> list[dict]:
    """Return strategy-compatible rule dicts for a Buy-The-Dip strategy.

    Generates rules that buy when price drops *dip_pct* % from a reference
    level, optionally confirm with a *recovery_pct* % bounce, and sell at
    *take_profit_pct* % gain.
    """
    if dip_pct <= 0:
        raise ValueError("dip_pct must be greater than 0")
    if dip_pct >= 100:
        raise ValueError("dip_pct must be less than 100")
    if recovery_pct < 0:
        raise ValueError("recovery_pct must be >= 0")
    if recovery_pct >= 100:
        raise ValueError("recovery_pct must be less than 100")
    if take_profit_pct <= 0:
        raise ValueError("take_profit_pct must be greater than 0")

    rules: list[dict] = []

    # Rule 1 – Dip detection (buy signal)
    rules.append({
        "conditions": [
            {"indicator": "price_change_pct", "operator": "lte", "value": -dip_pct},
        ],
        "action": "buy",
        "weight": 1.0,
        "description": f"BTD buy on {dip_pct:.1f}% dip",
        "amount": 1.0,
    })

    # Rule 2 – Recovery confirmation (buy signal, stronger) – only if recovery_pct > 0
    if recovery_pct > 0:
        rules.append({
            "conditions": [
                {"indicator": "price_change_pct", "operator": "lte", "value": -dip_pct},
                {"indicator": "price_recovery_pct", "operator": "gte", "value": recovery_pct},
            ],
            "action": "buy",
            "weight": 2.0,
            "description": f"BTD confirmed buy after {recovery_pct:.1f}% recovery",
            "amount": 1.0,
        })

    # Rule 3 – Take profit (sell signal)
    rules.append({
        "conditions": [
            {"indicator": "position_gain_pct", "operator": "gte", "value": take_profit_pct},
        ],
        "action": "sell",
        "weight": 1.0,
        "description": f"BTD take profit at {take_profit_pct:.1f}%",
        "amount": 1.0,
    })

    rules.sort(key=lambda r: r["weight"])
    return rules

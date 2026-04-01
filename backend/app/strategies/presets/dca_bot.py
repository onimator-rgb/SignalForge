"""DCA (Dollar-Cost Averaging) Bot preset – generate periodic buy rules."""

from __future__ import annotations


def generate_dca_rules(
    interval_hours: int,
    amount_per_buy: float,
    max_buys: int,
    price_drop_bonus_pct: float = 0.0,
) -> list[dict]:
    """Return strategy-compatible rule dicts for a DCA buying strategy.

    Generates rules for periodic buying every *interval_hours* hours,
    with an optional bonus buy when price drops by *price_drop_bonus_pct* %.
    Stops after *max_buys* total purchases.
    """
    if interval_hours <= 0:
        raise ValueError("interval_hours must be greater than 0")
    if amount_per_buy <= 0:
        raise ValueError("amount_per_buy must be greater than 0")
    if max_buys < 1:
        raise ValueError("max_buys must be >= 1")
    if price_drop_bonus_pct < 0:
        raise ValueError("price_drop_bonus_pct must be >= 0")
    if price_drop_bonus_pct >= 100:
        raise ValueError("price_drop_bonus_pct must be less than 100")

    rules: list[dict] = []

    # Rule 1 – Base DCA buy (periodic)
    rules.append({
        "conditions": [
            {"indicator": "hours_since_last_buy", "operator": "gte", "value": interval_hours},
        ],
        "action": "buy",
        "weight": 1.0,
        "description": f"DCA buy every {interval_hours}h",
        "amount": amount_per_buy,
    })

    # Rule 2 – Max buys guard (hold)
    rules.append({
        "conditions": [
            {"indicator": "total_buys", "operator": "gte", "value": max_buys},
        ],
        "action": "hold",
        "weight": 10.0,
        "description": f"DCA stop after {max_buys} buys",
        "amount": 0,
    })

    # Rule 3 – Price drop bonus buy (only if price_drop_bonus_pct > 0)
    if price_drop_bonus_pct > 0:
        rules.append({
            "conditions": [
                {"indicator": "hours_since_last_buy", "operator": "gte", "value": interval_hours},
                {"indicator": "price_change_pct", "operator": "lte", "value": -price_drop_bonus_pct},
            ],
            "action": "buy",
            "weight": 2.0,
            "description": f"DCA bonus buy on {price_drop_bonus_pct:.1f}% dip",
            "amount": amount_per_buy * 2,
        })

    rules.sort(key=lambda r: r["weight"])
    return rules

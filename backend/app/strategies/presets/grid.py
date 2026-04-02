"""Grid Bot preset – generate buy/sell rules at fixed price intervals."""

from __future__ import annotations


def generate_grid_rules(
    lower_price: float,
    upper_price: float,
    num_grids: int,
    amount_per_grid: float,
) -> list[dict]:
    """Return strategy-compatible rule dicts for grid trading.

    Generates BUY rules at evenly-spaced levels below the midpoint and
    SELL rules at levels above the midpoint.
    """
    if lower_price <= 0:
        raise ValueError("lower_price must be positive")
    if upper_price <= lower_price:
        raise ValueError("upper_price must be greater than lower_price")
    if num_grids < 2:
        raise ValueError("num_grids must be at least 2")
    if amount_per_grid <= 0:
        raise ValueError("amount_per_grid must be positive")

    step = (upper_price - lower_price) / num_grids
    levels = [lower_price + i * step for i in range(num_grids + 1)]
    midpoint = (lower_price + upper_price) / 2

    rules: list[dict] = []
    for level in levels:
        if level <= midpoint:
            rules.append({
                "conditions": [
                    {"indicator": "price", "operator": "lte", "value": level},
                ],
                "action": "buy",
                "weight": 1.0,
                "description": f"Grid buy at {level:.2f}",
                "amount": amount_per_grid,
            })
        else:
            rules.append({
                "conditions": [
                    {"indicator": "price", "operator": "gte", "value": level},
                ],
                "action": "sell",
                "weight": 1.0,
                "description": f"Grid sell at {level:.2f}",
                "amount": amount_per_grid,
            })

    rules.sort(key=lambda r: r["conditions"][0]["value"])
    return rules

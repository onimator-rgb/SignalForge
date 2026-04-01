"""DCA (Dollar Cost Averaging) engine — pure functions for position averaging down.

When an open position drops by a configurable percentage from its average entry,
automatically buy more at the lower price to reduce the average entry cost.
DCA state is stored in the existing exit_context JSONB column.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.portfolio.models import PortfolioPosition
    from app.strategy.profiles import StrategyProfile

# ── Constants ────────────────────────────────────────
DCA_MAX_LEVELS = 3
DCA_DROP_PCT = -0.05  # trigger when price drops 5% below avg entry
DCA_LEVEL_MULTIPLIERS = [0.5, 0.75, 1.0]  # fraction of original size per level


def get_dca_state(pos: PortfolioPosition) -> dict:
    """Extract DCA state from pos.exit_context or return defaults."""
    ctx = pos.exit_context
    if ctx and "dca" in ctx:
        return dict(ctx["dca"])
    return {
        "dca_level": 0,
        "dca_buys": [],
        "original_entry": float(pos.entry_price),
        "original_qty": float(pos.quantity),
    }


def should_dca(
    avg_entry: float,
    current_price: float,
    dca_level: int,
    max_levels: int = DCA_MAX_LEVELS,
    drop_pct: float = DCA_DROP_PCT,
) -> bool:
    """Return True if current_price has dropped enough to trigger next DCA level."""
    if dca_level >= max_levels:
        return False
    # Each successive level requires a deeper drop: 5%, 10%, 15% etc.
    threshold = avg_entry * (1 + drop_pct * (dca_level + 1))
    return current_price <= threshold


def calculate_dca_buy(
    original_value: float,
    dca_level: int,
    current_price: float,
    available_cash: float,
    min_position_usd: float,
) -> dict | None:
    """Compute the DCA buy size. Returns None if insufficient cash."""
    if dca_level >= len(DCA_LEVEL_MULTIPLIERS):
        return None

    target_value = original_value * DCA_LEVEL_MULTIPLIERS[dca_level]
    buy_value = min(target_value, available_cash)

    if buy_value < min_position_usd:
        return None

    return {
        "buy_value": round(buy_value, 2),
        "quantity": buy_value / current_price,
        "price": current_price,
    }


def apply_dca_to_position(
    pos: PortfolioPosition,
    dca_buy: dict,
    profile: StrategyProfile,
) -> dict:
    """Update position in-place after a DCA buy. Returns updated DCA state."""
    old_entry = float(pos.entry_price)
    old_qty = float(pos.quantity)
    buy_price = dca_buy["price"]
    buy_qty = dca_buy["quantity"]

    # Weighted average entry
    new_avg = (old_entry * old_qty + buy_price * buy_qty) / (old_qty + buy_qty)
    new_qty = old_qty + buy_qty
    new_value = float(pos.entry_value_usd) + dca_buy["buy_value"]

    pos.entry_price = round(new_avg, 8)
    pos.quantity = round(new_qty, 8)
    pos.entry_value_usd = round(new_value, 2)

    # Recalculate stop loss and take profit relative to new average
    pos.stop_loss_price = round(new_avg * (1 + profile.stop_loss_pct), 8)
    pos.take_profit_price = round(new_avg * (1 + profile.take_profit_pct), 8)

    # Update DCA state in exit_context
    dca_state = get_dca_state(pos)
    dca_state["dca_level"] += 1
    dca_state["dca_buys"].append({
        "level": dca_state["dca_level"],
        "price": buy_price,
        "quantity": buy_qty,
        "value": dca_buy["buy_value"],
        "new_avg_entry": round(new_avg, 8),
    })

    ctx = dict(pos.exit_context) if pos.exit_context else {}
    ctx["dca"] = dca_state
    pos.exit_context = ctx

    return dca_state

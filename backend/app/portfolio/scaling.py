"""Position Scaling Up engine — pure functions for adding to winning positions.

When an open position is profitable by a configurable percentage and the
recommendation is still active, allow adding a scale-up tranche.
Max 1 scale-up per position. Tranche = 50 % of original position value.
After scale-up the stop loss moves to break-even (original entry price)
to protect the already-earned profit.
Scale-up state is stored in the existing exit_context JSONB column.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.portfolio.models import PortfolioPosition
    from app.strategy.profiles import StrategyProfile

# ── Constants ────────────────────────────────────────
SCALE_UP_MAX = 1  # max 1 scale-up per position
SCALE_UP_PROFIT_TRIGGER = 0.08  # 8 % unrealised profit to trigger
SCALE_UP_SIZE_PCT = 0.50  # tranche = 50 % of original position value


def get_scale_state(pos: PortfolioPosition) -> dict:
    """Extract scale-up state from pos.exit_context or return defaults."""
    ctx = pos.exit_context
    if ctx and "scale" in ctx:
        return dict(ctx["scale"])
    return {
        "scale_level": 0,
        "scale_ups": [],
        "original_entry": float(pos.entry_price),
        "original_qty": float(pos.quantity),
    }


def should_scale_up(
    avg_entry: float,
    current_price: float,
    scale_level: int,
    max_levels: int = SCALE_UP_MAX,
    profit_trigger: float = SCALE_UP_PROFIT_TRIGGER,
) -> bool:
    """Return True if unrealised profit >= profit_trigger and scale_level < max_levels."""
    if scale_level >= max_levels:
        return False
    profit_pct = (current_price - avg_entry) / avg_entry
    return profit_pct >= profit_trigger


def calculate_scale_buy(
    original_value: float,
    current_price: float,
    available_cash: float,
    min_position_usd: float,
    size_pct: float = SCALE_UP_SIZE_PCT,
) -> dict | None:
    """Compute the scale-up buy size. Returns None if insufficient cash."""
    target_value = original_value * size_pct
    buy_value = min(target_value, available_cash)

    if buy_value < min_position_usd:
        return None

    return {
        "buy_value": round(buy_value, 2),
        "quantity": buy_value / current_price,
        "price": current_price,
    }


def apply_scale_to_position(
    pos: PortfolioPosition,
    scale_buy: dict,
    profile: StrategyProfile,
) -> dict:
    """Update position in-place after a scale-up buy. Returns updated scale state."""
    # Capture scale state BEFORE mutating position fields
    scale_state = get_scale_state(pos)
    original_entry = scale_state["original_entry"]

    old_entry = float(pos.entry_price)
    old_qty = float(pos.quantity)
    buy_price = scale_buy["price"]
    buy_qty = scale_buy["quantity"]

    # Weighted average entry
    new_avg = (old_entry * old_qty + buy_price * buy_qty) / (old_qty + buy_qty)
    new_qty = old_qty + buy_qty
    new_value = float(pos.entry_value_usd) + scale_buy["buy_value"]

    pos.entry_price = round(new_avg, 8)
    pos.quantity = round(new_qty, 8)
    pos.entry_value_usd = round(new_value, 2)

    # Move stop loss to break-even (original entry price) to protect profit
    pos.stop_loss_price = round(original_entry, 8)

    # Recalculate take profit relative to new average
    pos.take_profit_price = round(new_avg * (1 + profile.take_profit_pct), 8)

    # Update scale state in exit_context
    scale_state["scale_level"] += 1
    scale_state["scale_ups"].append({
        "level": scale_state["scale_level"],
        "price": buy_price,
        "quantity": buy_qty,
        "value": scale_buy["buy_value"],
        "new_avg_entry": round(new_avg, 8),
    })

    ctx = dict(pos.exit_context) if pos.exit_context else {}
    ctx["scale"] = scale_state
    pos.exit_context = ctx

    return scale_state

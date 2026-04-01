"""DCA (Dollar Cost Averaging) engine — pure functions for position averaging down.

When an open position drops by a configurable percentage from its average entry,
automatically buy more at the lower price to reduce the average entry cost.
DCA state is stored in the existing exit_context JSONB column.

The module provides two layers:
1. **Pure-logic layer** — DCAConfig dataclass + stateless functions (should_dca_pure,
   compute_dca_order, compute_new_avg_price) that depend only on their arguments.
2. **Position-aware layer** — helpers that read/write PortfolioPosition objects
   (get_dca_state, should_dca, calculate_dca_buy, apply_dca_to_position).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.portfolio.models import PortfolioPosition
    from app.strategy.profiles import StrategyProfile


# ── Pure-logic DCA layer ────────────────────────────────


@dataclass(frozen=True)
class DCAConfig:
    """Configuration for dollar-cost averaging strategy.

    Attributes:
        max_levels: Maximum number of DCA buy-ins after the initial entry.
        drop_trigger_pct: Percentage drops from entry that trigger each DCA
            level. Must be positive, strictly increasing, and have length
            equal to *max_levels*.
        tranche_pcts: Fraction of remaining capital allocated to each DCA
            tranche. Must have length equal to *max_levels* and sum to ~1.0.
    """

    max_levels: int = 3
    drop_trigger_pct: list[float] = field(
        default_factory=lambda: [5.0, 10.0, 20.0],
    )
    tranche_pcts: list[float] = field(
        default_factory=lambda: [0.3, 0.4, 0.3],
    )

    def __post_init__(self) -> None:
        if len(self.drop_trigger_pct) != self.max_levels:
            raise ValueError(
                f"drop_trigger_pct length ({len(self.drop_trigger_pct)}) "
                f"must equal max_levels ({self.max_levels})"
            )
        if len(self.tranche_pcts) != self.max_levels:
            raise ValueError(
                f"tranche_pcts length ({len(self.tranche_pcts)}) "
                f"must equal max_levels ({self.max_levels})"
            )
        if not all(p > 0 for p in self.drop_trigger_pct):
            raise ValueError("All drop_trigger_pct values must be positive")
        for i in range(1, len(self.drop_trigger_pct)):
            if self.drop_trigger_pct[i] <= self.drop_trigger_pct[i - 1]:
                raise ValueError(
                    "drop_trigger_pct values must be strictly increasing"
                )
        if abs(sum(self.tranche_pcts) - 1.0) > 1e-6:
            raise ValueError(
                f"tranche_pcts must sum to ~1.0, got {sum(self.tranche_pcts)}"
            )


def should_dca_pure(
    current_price: float,
    entry_price: float,
    dca_levels_used: int,
    config: DCAConfig,
) -> bool:
    """Decide whether to add to a position via DCA.

    Returns True only when the price has dropped at least as much as the
    trigger for the *next* DCA level and more levels remain.
    """
    if dca_levels_used >= config.max_levels:
        return False
    if current_price >= entry_price:
        return False
    drop_pct = (entry_price - current_price) / entry_price * 100.0
    return drop_pct >= config.drop_trigger_pct[dca_levels_used]


def compute_dca_order(
    remaining_capital: float,
    dca_levels_used: int,
    config: DCAConfig,
) -> float:
    """Return the USD amount for the next DCA tranche.

    Raises ValueError if all DCA levels have been exhausted.
    """
    if dca_levels_used >= config.max_levels:
        raise ValueError(
            f"All {config.max_levels} DCA levels already used"
        )
    if remaining_capital <= 0:
        return 0.0
    return remaining_capital * config.tranche_pcts[dca_levels_used]


def compute_new_avg_price(
    current_avg: float,
    current_qty: float,
    new_price: float,
    new_qty: float,
) -> float:
    """Return the weighted-average entry price after adding shares.

    Raises ValueError if total quantity would be zero.
    """
    total_qty = current_qty + new_qty
    if total_qty == 0:
        raise ValueError("Total quantity must not be zero")
    return (current_avg * current_qty + new_price * new_qty) / total_qty

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

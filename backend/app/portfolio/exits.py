"""Exit engine v1 — smart exit rules for demo portfolio positions.

Priority order:
  1. Hard stop loss
  2. Trailing stop hit
  3. Take profit
  4. Break-even protection
  5. Signal deterioration
  6. Max hold

Regime modifiers (risk_off):
  - Break-even arm lowered by 1%
  - Trailing arm lowered by 1%
"""

from datetime import datetime

from app.logging_config import get_logger
from app.portfolio.models import PortfolioPosition
from app.strategy.profiles import StrategyProfile

log = get_logger(__name__)

BREAK_EVEN_CUSHION = 0.002  # 0.2% above entry for break-even close


def evaluate_exit(
    pos: PortfolioPosition,
    current_price: float,
    profile: StrategyProfile,
    regime: str,
    rec_score: float | None = None,
    rec_type: str | None = None,
    now: datetime | None = None,
) -> tuple[str | None, dict]:
    """Evaluate exit rules for a position. Returns (close_reason, context) or (None, {})."""
    entry = float(pos.entry_price)
    if entry <= 0:
        return None, {}

    pnl_pct = (current_price - entry) / entry
    peak = float(pos.peak_price) if pos.peak_price else entry
    peak_pnl = float(pos.peak_pnl_pct or 0) / 100.0

    # Regime adjustments
    regime_offset = 0.01 if regime == "risk_off" else 0.0
    effective_be_arm = profile.break_even_arm_pct - regime_offset
    effective_trail_arm = profile.trailing_arm_pct - regime_offset

    context = {
        "entry_price": entry,
        "current_price": current_price,
        "pnl_pct": round(pnl_pct * 100, 4),
        "peak_price": peak,
        "peak_pnl_pct": round(peak_pnl * 100, 4),
        "regime": regime,
        "profile": profile.name,
    }

    # ── Rule A: Hard stop loss ────────────────────
    if pnl_pct <= profile.stop_loss_pct:
        context["rule"] = "stop_loss"
        context["threshold"] = profile.stop_loss_pct
        return "stop_hit", context

    # ── Rule B (update state): Track peak ─────────
    new_peak = max(peak, current_price)
    new_peak_pnl = (new_peak - entry) / entry

    # ── Rule C: Trailing stop ─────────────────────
    if new_peak_pnl >= effective_trail_arm and pos.trailing_stop_price:
        trail_price = float(pos.trailing_stop_price)
        if current_price <= trail_price:
            context["rule"] = "trailing_stop"
            context["trailing_stop_price"] = trail_price
            context["peak_at_close"] = new_peak
            return "trailing_stop_hit", context

    # ── Rule D: Take profit ───────────────────────
    if pnl_pct >= profile.take_profit_pct:
        context["rule"] = "take_profit"
        return "target_hit", context

    # ── Rule E: Break-even protection ─────────────
    if pos.break_even_armed and pnl_pct <= BREAK_EVEN_CUSHION:
        context["rule"] = "break_even_protect"
        context["armed_at_pnl"] = round(peak_pnl * 100, 2)
        return "break_even_protect", context

    # ── Rule F: Signal deterioration ──────────────
    if rec_type == "avoid" and pnl_pct < 0.02:
        context["rule"] = "signal_deterioration"
        context["rec_score"] = rec_score
        context["rec_type"] = rec_type
        return "signal_deterioration", context

    # ── Rule G: Max hold ──────────────────────────
    if now and pos.max_hold_until and now >= pos.max_hold_until:
        context["rule"] = "max_hold"
        return "max_hold", context

    return None, {}


def update_position_state(
    pos: PortfolioPosition,
    current_price: float,
    profile: StrategyProfile,
    regime: str,
) -> bool:
    """Update peak, trailing stop, break-even state. Returns True if changed."""
    entry = float(pos.entry_price)
    if entry <= 0:
        return False

    changed = False
    pnl_pct = (current_price - entry) / entry
    peak = float(pos.peak_price) if pos.peak_price else entry

    # Regime adjustments
    regime_offset = 0.01 if regime == "risk_off" else 0.0
    effective_be_arm = profile.break_even_arm_pct - regime_offset
    effective_trail_arm = profile.trailing_arm_pct - regime_offset

    # Update peak
    if current_price > peak:
        pos.peak_price = current_price
        pos.peak_pnl_pct = round(pnl_pct * 100, 4)
        peak = current_price
        changed = True

    # Arm break-even
    if not pos.break_even_armed and pnl_pct >= effective_be_arm:
        pos.break_even_armed = True
        changed = True
        log.info("portfolio.break_even_armed", pnl_pct=round(pnl_pct * 100, 2))

    # Arm / update trailing stop
    peak_pnl = (peak - entry) / entry
    if peak_pnl >= effective_trail_arm:
        new_trail = round(peak * (1 - profile.trailing_pct), 8)
        old_trail = float(pos.trailing_stop_price) if pos.trailing_stop_price else 0
        if new_trail > old_trail:
            pos.trailing_stop_price = new_trail
            changed = True
            if old_trail == 0:
                log.info("portfolio.trailing_armed", trail_price=new_trail, peak=peak)

    return changed

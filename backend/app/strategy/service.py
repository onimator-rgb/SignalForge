"""Auto strategy profile switch — maps market regime to strategy profile.

When STRATEGY_AUTO_SWITCH is enabled, the system automatically selects
the optimal strategy profile based on detected market regime.
Detects regime transitions and applies new profile parameters to open positions.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger
from app.portfolio.models import PortfolioPosition
from app.strategy.profiles import PROFILES, StrategyProfile
from app.strategy.regime import calculate_regime

log = get_logger(__name__)

REGIME_TO_PROFILE: dict[str, str] = {
    "risk_on": "aggressive",
    "neutral": "balanced",
    "risk_off": "conservative",
}

# Module-level regime tracker (resets on process restart)
_last_regime: str | None = None


def detect_regime_transition(current_regime: str) -> tuple[bool, str | None]:
    """Detect if market regime has changed since last check.

    Args:
        current_regime: The current regime string.

    Returns:
        (changed, previous_regime) — changed is True if regime differs
        from the last known regime (and last regime was not None).
    """
    global _last_regime
    previous = _last_regime
    _last_regime = current_regime

    if previous is not None and previous != current_regime:
        return True, previous
    return False, None


async def apply_profile_to_open_positions(
    db: AsyncSession, profile: StrategyProfile,
) -> int:
    """Apply new regime profile parameters to all open positions.

    Updates the exit_context JSONB field with regime-specific stop-loss,
    take-profit, and trailing parameters.

    Returns:
        Count of updated positions.
    """
    result = await db.execute(
        select(PortfolioPosition).where(PortfolioPosition.status == "open")
    )
    positions = list(result.scalars().all())
    if not positions:
        return 0

    now_iso = datetime.utcnow().isoformat()
    count = 0
    for pos in positions:
        ctx = dict(pos.exit_context) if pos.exit_context else {}
        ctx["regime_stop_loss"] = profile.stop_loss_pct
        ctx["regime_take_profit"] = profile.take_profit_pct
        ctx["regime_trailing_pct"] = profile.trailing_pct
        ctx["regime_profile"] = profile.name
        ctx["regime_switched_at"] = now_iso
        pos.exit_context = ctx
        count += 1

    log.info(
        "strategy.profile_applied_to_positions",
        profile=profile.name,
        positions_updated=count,
    )
    return count


async def auto_select_profile(
    db: AsyncSession,
) -> tuple[StrategyProfile, dict]:
    """Select strategy profile based on current market regime.

    Calls calculate_regime() and maps the result to the appropriate
    strategy profile via REGIME_TO_PROFILE. Detects regime transitions
    and applies new profile parameters to open positions.

    Returns:
        Tuple of (StrategyProfile, regime_info dict).
    """
    regime_info = await calculate_regime(db)
    regime = regime_info["regime"]
    profile_name = REGIME_TO_PROFILE.get(regime, "balanced")
    profile = PROFILES[profile_name]

    # Detect regime transition
    changed, old_regime = detect_regime_transition(regime)
    positions_updated = 0
    if changed:
        log.info(
            "strategy.regime_transition",
            from_regime=old_regime,
            to_regime=regime,
            profile=profile_name,
        )
        positions_updated = await apply_profile_to_open_positions(db, profile)

    regime_info["transition"] = {
        "changed": changed,
        "from": old_regime,
        "to": regime,
        "positions_updated": positions_updated,
    }

    log.info(
        "strategy.auto_select",
        regime=regime,
        selected_profile=profile_name,
    )

    return profile, regime_info

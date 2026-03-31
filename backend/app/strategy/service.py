"""Auto strategy profile switch — maps market regime to strategy profile.

When STRATEGY_AUTO_SWITCH is enabled, the system automatically selects
the optimal strategy profile based on detected market regime.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger
from app.strategy.profiles import PROFILES, StrategyProfile
from app.strategy.regime import calculate_regime

log = get_logger(__name__)

REGIME_TO_PROFILE: dict[str, str] = {
    "risk_on": "aggressive",
    "neutral": "balanced",
    "risk_off": "conservative",
}


async def auto_select_profile(
    db: AsyncSession,
) -> tuple[StrategyProfile, dict]:
    """Select strategy profile based on current market regime.

    Calls calculate_regime() and maps the result to the appropriate
    strategy profile via REGIME_TO_PROFILE.

    Returns:
        Tuple of (StrategyProfile, regime_info dict).
    """
    regime_info = await calculate_regime(db)
    regime = regime_info["regime"]
    profile_name = REGIME_TO_PROFILE.get(regime, "balanced")
    profile = PROFILES[profile_name]

    log.info(
        "strategy.auto_select",
        regime=regime,
        selected_profile=profile_name,
    )

    return profile, regime_info

"""Strategy endpoints — profile, regime, summary."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.strategy.profiles import get_active_profile, get_profile_dict, is_auto_switch_enabled, PROFILES
from app.strategy.regime import calculate_regime
from app.strategy.service import auto_select_profile

router = APIRouter(prefix="/api/v1/strategy", tags=["strategy"])


@router.get("/profile")
async def strategy_profile():
    """Get active strategy profile and all available profiles."""
    active = get_active_profile()
    return {
        "active": get_profile_dict(active),
        "available": list(PROFILES.keys()),
    }


@router.get("/regime")
async def market_regime(db: AsyncSession = Depends(get_db)):
    """Get current market regime (risk_on / neutral / risk_off)."""
    return await calculate_regime(db)


@router.get("/summary")
async def strategy_summary(db: AsyncSession = Depends(get_db)):
    """Combined strategy state: profile + regime + effective settings."""
    auto_enabled = is_auto_switch_enabled()

    # Auto-switch: select profile from regime; otherwise use static config
    if auto_enabled:
        active, regime = await auto_select_profile(db)
    else:
        active = get_active_profile()
        regime = await calculate_regime(db)

    from app.strategy.regime import get_regime_score_adjustment, get_regime_position_multiplier
    score_adj = get_regime_score_adjustment(regime["regime"])
    pos_mult = get_regime_position_multiplier(regime["regime"])

    effective_threshold = active.candidate_buy_threshold - score_adj
    effective_position = round(active.max_position_pct * pos_mult, 4)

    # Always compute recommended profile for the auto_switch section
    from app.strategy.service import REGIME_TO_PROFILE
    recommended_profile = REGIME_TO_PROFILE.get(regime["regime"], "balanced")

    return {
        "profile": get_profile_dict(active),
        "regime": regime,
        "effective": {
            "candidate_buy_threshold": effective_threshold,
            "max_position_pct": effective_position,
            "score_adjustment": score_adj,
            "position_multiplier": pos_mult,
            "note": f"Profile '{active.name}' + regime '{regime['regime']}' → threshold={effective_threshold}, position={effective_position*100:.1f}%",
        },
        "auto_switch": {
            "enabled": auto_enabled,
            "recommended_profile": recommended_profile,
            "reason": regime["regime"],
        },
    }

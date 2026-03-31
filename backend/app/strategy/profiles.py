"""Strategy profiles — config-driven trading behavior presets.

Active profile is set via STRATEGY_PROFILE env var (default: balanced).
"""

from dataclasses import dataclass

from app.config import settings
from app.logging_config import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class StrategyProfile:
    name: str
    candidate_buy_threshold: float
    min_confidence: str
    allow_high_risk: bool
    max_position_pct: float
    stop_loss_pct: float
    take_profit_pct: float
    max_hold_hours: int
    # Exit engine v1
    trailing_pct: float
    trailing_arm_pct: float
    break_even_arm_pct: float
    # Trailing buy entry
    trailing_buy_bounce_pct: float
    trailing_buy_max_hours: int


PROFILES: dict[str, StrategyProfile] = {
    "conservative": StrategyProfile(
        name="conservative",
        candidate_buy_threshold=68,
        min_confidence="high",
        allow_high_risk=False,
        max_position_pct=0.12,
        stop_loss_pct=-0.05,
        take_profit_pct=0.10,
        max_hold_hours=48,
        trailing_pct=0.03,
        trailing_arm_pct=0.05,
        break_even_arm_pct=0.03,
        trailing_buy_bounce_pct=0.02,
        trailing_buy_max_hours=12,
    ),
    "balanced": StrategyProfile(
        name="balanced",
        candidate_buy_threshold=63,
        min_confidence="medium",
        allow_high_risk=False,
        max_position_pct=0.20,
        stop_loss_pct=-0.08,
        take_profit_pct=0.15,
        max_hold_hours=72,
        trailing_pct=0.05,
        trailing_arm_pct=0.06,
        break_even_arm_pct=0.04,
        trailing_buy_bounce_pct=0.015,
        trailing_buy_max_hours=18,
    ),
    "aggressive": StrategyProfile(
        name="aggressive",
        candidate_buy_threshold=58,
        min_confidence="medium",
        allow_high_risk=True,
        max_position_pct=0.25,
        stop_loss_pct=-0.12,
        take_profit_pct=0.22,
        max_hold_hours=96,
        trailing_pct=0.07,
        trailing_arm_pct=0.08,
        break_even_arm_pct=0.05,
        trailing_buy_bounce_pct=0.01,
        trailing_buy_max_hours=24,
    ),
}


def get_active_profile() -> StrategyProfile:
    name = getattr(settings, "STRATEGY_PROFILE", "balanced")
    return PROFILES.get(name, PROFILES["balanced"])


def get_profile_dict(profile: StrategyProfile) -> dict:
    return {
        "name": profile.name,
        "candidate_buy_threshold": profile.candidate_buy_threshold,
        "min_confidence": profile.min_confidence,
        "allow_high_risk": profile.allow_high_risk,
        "max_position_pct": profile.max_position_pct,
        "stop_loss_pct": profile.stop_loss_pct,
        "take_profit_pct": profile.take_profit_pct,
        "max_hold_hours": profile.max_hold_hours,
        "trailing_pct": profile.trailing_pct,
        "trailing_arm_pct": profile.trailing_arm_pct,
        "break_even_arm_pct": profile.break_even_arm_pct,
        "trailing_buy_bounce_pct": profile.trailing_buy_bounce_pct,
        "trailing_buy_max_hours": profile.trailing_buy_max_hours,
    }

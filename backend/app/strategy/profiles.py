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
    min_confidence: str  # "low", "medium", "high"
    allow_high_risk: bool
    max_position_pct: float
    stop_loss_pct: float
    take_profit_pct: float
    max_hold_hours: int


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
    ),
}


def get_active_profile() -> StrategyProfile:
    """Get the currently active strategy profile."""
    name = getattr(settings, "STRATEGY_PROFILE", "balanced")
    profile = PROFILES.get(name, PROFILES["balanced"])
    return profile


def get_profile_dict(profile: StrategyProfile) -> dict:
    """Convert profile to dict for API response."""
    return {
        "name": profile.name,
        "candidate_buy_threshold": profile.candidate_buy_threshold,
        "min_confidence": profile.min_confidence,
        "allow_high_risk": profile.allow_high_risk,
        "max_position_pct": profile.max_position_pct,
        "stop_loss_pct": profile.stop_loss_pct,
        "take_profit_pct": profile.take_profit_pct,
        "max_hold_hours": profile.max_hold_hours,
    }

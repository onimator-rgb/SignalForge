"""Trailing buy entry mechanism — pure functions, no DB I/O.

After a buy signal fires, trail price downward to find a local bottom.
Execute the buy when price bounces X% above the trailing low.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass
class TrailingBuyState:
    """Snapshot of a trailing buy entry attempt."""

    asset_id: str
    recommendation_id: str
    signal_price: float
    lowest_price: float
    bounce_pct: float
    started_at: str  # ISO-8601
    expires_at: str  # ISO-8601
    status: str  # 'trailing' | 'triggered' | 'expired'


def start_trailing(
    signal_price: float,
    bounce_pct: float,
    max_hours: int,
    now: datetime,
) -> dict[str, Any]:
    """Return context_data dict for a new trailing buy EntryDecision."""
    started_at = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    expires_at = started_at + timedelta(hours=max_hours)
    return {
        "signal_price": signal_price,
        "lowest_price": signal_price,
        "bounce_pct": bounce_pct,
        "started_at": started_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "status": "trailing",
    }


def update_trailing(
    context_data: dict[str, Any],
    current_price: float,
    now: datetime,
) -> tuple[str, dict[str, Any]]:
    """Update trailing state and decide action.

    Returns (action, updated_context) where action is one of:
      - 'continue': still trailing, no action needed
      - 'buy': price bounced above threshold, execute the buy
      - 'expired': trailing window elapsed without a bounce
    """
    ctx = dict(context_data)  # shallow copy
    expires_at = datetime.fromisoformat(ctx["expires_at"])
    now_aware = now if now.tzinfo else now.replace(tzinfo=timezone.utc)

    # Track new lows
    lowest = min(ctx["lowest_price"], current_price)
    ctx["lowest_price"] = lowest

    # Check bounce
    bounce_pct: float = ctx["bounce_pct"]
    if current_price >= lowest * (1 + bounce_pct):
        ctx["status"] = "triggered"
        return "buy", ctx

    # Check expiry
    if now_aware >= expires_at:
        ctx["status"] = "expired"
        return "expired", ctx

    # Still trailing
    return "continue", ctx

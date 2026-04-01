"""Portfolio protections layer v1 — entry guards for demo portfolio.

Protection rules (checked before opening new positions):
  A. Asset cooldown — no re-entry on recently closed asset
  B. Stoploss guard — pause after consecutive losses
  B2. Consecutive SL guard — pause after N consecutive stop-loss exits
  C. Asset class exposure cap — limit concentration per class
  D. Entry frequency cap — limit new positions per time window
  E. Risk-off extra restriction
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.logging_config import get_logger
from app.portfolio.models import Portfolio, PortfolioPosition, ProtectionEvent
from app.portfolio.rules import DAILY_DRAWDOWN_LIMIT_PCT

log = get_logger(__name__)

# ── Config ────────────────────────────────────────

ASSET_COOLDOWN_HOURS = 24
COOLDOWN_AFTER_LOSS_HOURS = 48
COOLDOWN_AFTER_PROFIT_HOURS = 12
STOPLOSS_GUARD_LOOKBACK_HOURS = 12
STOPLOSS_GUARD_MAX_LOSSES = 2
STOPLOSS_GUARD_LOCK_HOURS = 6
MAX_PER_CLASS = 3  # max open positions per asset_class
MAX_NEW_POSITIONS_PER_6H = 2
CONSECUTIVE_SL_THRESHOLD = 3
CONSECUTIVE_SL_LOCK_MINUTES = 120


async def check_protections(
    db: AsyncSession,
    portfolio_id: uuid.UUID,
    asset_id: uuid.UUID,
    asset_class: str,
    regime: str,
    now: datetime | None = None,
) -> tuple[bool, str | None, str | None]:
    """Check all protection rules for a candidate entry.

    Returns:
        (allowed, protection_type, reason) — allowed=True means entry OK.
    """
    now = now or datetime.now(timezone.utc)

    # Expire old protections
    await _expire_protections(db, now)

    # A. Asset cooldown (loss-aware)
    blocked, reason, cooldown_hours = await _check_asset_cooldown(db, portfolio_id, asset_id, now)
    if blocked:
        assert reason is not None
        await _log_protection(db, "asset_cooldown", reason, asset_id=asset_id, now=now,
                              expires=now + timedelta(hours=cooldown_hours))
        return False, "asset_cooldown", reason

    # B. Stoploss guard
    blocked, reason = await _check_stoploss_guard(db, portfolio_id, now)
    if blocked:
        return False, "stoploss_guard", reason

    # B2. Consecutive stop-loss guard
    blocked, reason = await _check_consecutive_sl(db, portfolio_id, now)
    if blocked:
        return False, "consecutive_sl_guard", reason

    # C. Asset class exposure
    blocked, reason = await _check_class_exposure(db, portfolio_id, asset_class)
    if blocked:
        return False, "class_exposure_cap", reason

    # D. Entry frequency cap
    blocked, reason = await _check_entry_frequency(db, portfolio_id, now)
    if blocked:
        return False, "entry_frequency_cap", reason

    # F. Daily drawdown guard
    allowed, ptype, dd_reason = await _daily_drawdown_guard(db, portfolio_id, now)
    if not allowed:
        return False, ptype, dd_reason

    # E. Risk-off extra restriction
    if regime == "risk_off":
        # Already handled by portfolio service (higher threshold, only high confidence)
        # Additional: block medium confidence entirely in risk_off
        pass  # Handled at caller level

    return True, None, None


async def get_active_protections(db: AsyncSession, portfolio_id: uuid.UUID) -> list[dict]:
    """Get currently active protection events."""
    now = datetime.now(timezone.utc)
    await _expire_protections(db, now)

    result = await db.execute(
        select(ProtectionEvent)
        .where(ProtectionEvent.status == "active")
        .order_by(ProtectionEvent.triggered_at.desc())
        .limit(20)
    )
    return [
        {
            "id": str(p.id),
            "type": p.protection_type,
            "status": p.status,
            "asset_class": p.asset_class,
            "reason": p.reason,
            "triggered_at": p.triggered_at.isoformat(),
            "expires_at": p.expires_at.isoformat() if p.expires_at else None,
        }
        for p in result.scalars().all()
    ]


# ── Protection rules ──────────────────────────────

async def _check_asset_cooldown(
    db: AsyncSession, portfolio_id: uuid.UUID, asset_id: uuid.UUID, now: datetime
) -> tuple[bool, str | None, int]:
    """Loss-aware cooldown: longer cooldown after a losing trade.
    Returns (blocked, reason, cooldown_hours)."""
    result = await db.execute(
        select(PortfolioPosition).where(
            PortfolioPosition.portfolio_id == portfolio_id,
            PortfolioPosition.asset_id == asset_id,
            PortfolioPosition.status == "closed",
            PortfolioPosition.closed_at.isnot(None),
        ).order_by(PortfolioPosition.closed_at.desc()).limit(1)
    )
    position = result.scalars().first()
    if position is None or position.closed_at is None:
        return False, None, 0

    cooldown_hours = (
        COOLDOWN_AFTER_LOSS_HOURS
        if position.realized_pnl_usd is not None and float(position.realized_pnl_usd) < 0
        else COOLDOWN_AFTER_PROFIT_HOURS
    )

    if now - position.closed_at < timedelta(hours=cooldown_hours):
        label = "loss" if cooldown_hours == COOLDOWN_AFTER_LOSS_HOURS else "profit"
        return True, f"Asset closed at {label} within last {cooldown_hours}h", cooldown_hours
    return False, None, 0


async def _check_stoploss_guard(
    db: AsyncSession, portfolio_id: uuid.UUID, now: datetime
) -> tuple[bool, str | None]:
    # Check if guard is already active
    active = await db.execute(
        select(func.count()).where(
            ProtectionEvent.protection_type == "stoploss_guard",
            ProtectionEvent.status == "active",
        )
    )
    if active.scalar_one() > 0:
        return True, "Stoploss guard active — cooling down after losses"

    # Check recent losses
    cutoff = now - timedelta(hours=STOPLOSS_GUARD_LOOKBACK_HOURS)
    losses = await db.execute(
        select(func.count()).where(
            PortfolioPosition.portfolio_id == portfolio_id,
            PortfolioPosition.status == "closed",
            PortfolioPosition.closed_at >= cutoff,
            PortfolioPosition.close_reason.in_(["stop_hit", "trailing_stop_hit"]),
            PortfolioPosition.realized_pnl_usd < 0,
        )
    )
    loss_count = losses.scalar_one()
    if loss_count >= STOPLOSS_GUARD_MAX_LOSSES:
        expires = now + timedelta(hours=STOPLOSS_GUARD_LOCK_HOURS)
        await _log_protection(
            db, "stoploss_guard",
            f"{loss_count} stop losses in {STOPLOSS_GUARD_LOOKBACK_HOURS}h — locked for {STOPLOSS_GUARD_LOCK_HOURS}h",
            now=now, expires=expires,
        )
        return True, f"{loss_count} stop losses triggered guard"
    return False, None


async def _check_class_exposure(
    db: AsyncSession, portfolio_id: uuid.UUID, asset_class: str
) -> tuple[bool, str | None]:
    result = await db.execute(
        select(func.count())
        .select_from(PortfolioPosition)
        .join(Asset, PortfolioPosition.asset_id == Asset.id)
        .where(
            PortfolioPosition.portfolio_id == portfolio_id,
            PortfolioPosition.status == "open",
            Asset.asset_class == asset_class,
        )
    )
    count = result.scalar_one()
    if count >= MAX_PER_CLASS:
        return True, f"{asset_class} exposure at cap ({count}/{MAX_PER_CLASS})"
    return False, None


async def _check_entry_frequency(
    db: AsyncSession, portfolio_id: uuid.UUID, now: datetime
) -> tuple[bool, str | None]:
    cutoff = now - timedelta(hours=6)
    result = await db.execute(
        select(func.count()).where(
            PortfolioPosition.portfolio_id == portfolio_id,
            PortfolioPosition.opened_at >= cutoff,
        )
    )
    recent = result.scalar_one()
    if recent >= MAX_NEW_POSITIONS_PER_6H:
        return True, f"{recent} entries in last 6h (cap={MAX_NEW_POSITIONS_PER_6H})"
    return False, None


async def _check_consecutive_sl(
    db: AsyncSession, portfolio_id: uuid.UUID, now: datetime
) -> tuple[bool, str | None]:
    # Check if guard is already active
    active = await db.execute(
        select(func.count()).where(
            ProtectionEvent.protection_type == "consecutive_sl_guard",
            ProtectionEvent.status == "active",
        )
    )
    if active.scalar_one() > 0:
        return True, "Consecutive SL guard active — cooling down"

    # Query last N closed positions ordered by closed_at DESC
    result = await db.execute(
        select(PortfolioPosition.close_reason)
        .where(
            PortfolioPosition.portfolio_id == portfolio_id,
            PortfolioPosition.status == "closed",
            PortfolioPosition.closed_at.isnot(None),
        )
        .order_by(PortfolioPosition.closed_at.desc())
        .limit(CONSECUTIVE_SL_THRESHOLD)
    )
    reasons = result.scalars().all()

    if len(reasons) < CONSECUTIVE_SL_THRESHOLD:
        return False, None

    stop_reasons = {"stop_hit", "trailing_stop_hit"}
    if all(r in stop_reasons for r in reasons):
        reason = (
            f"{CONSECUTIVE_SL_THRESHOLD} consecutive stop losses "
            f"— locked for {CONSECUTIVE_SL_LOCK_MINUTES}min"
        )
        expires = now + timedelta(minutes=CONSECUTIVE_SL_LOCK_MINUTES)
        await _log_protection(db, "consecutive_sl_guard", reason, now=now, expires=expires)
        return True, reason

    return False, None


async def _daily_drawdown_guard(
    db: AsyncSession, portfolio_id: uuid.UUID, now: datetime
) -> tuple[bool, str | None, str | None]:
    """Halt all new entries if equity dropped >DAILY_DRAWDOWN_LIMIT_PCT from day-open.

    Returns (allowed, protection_type, reason).
    """
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    # 1. Already blocked today?
    active_block = await db.execute(
        select(func.count()).where(
            ProtectionEvent.protection_type == "daily_drawdown",
            ProtectionEvent.status == "active",
            ProtectionEvent.triggered_at >= day_start,
        )
    )
    if active_block.scalar_one() > 0:
        return False, "daily_drawdown", "Daily drawdown circuit breaker active — entries halted for remainder of UTC day"

    # 2. Compute current equity = cash + sum(open position entry values)
    portfolio_result = await db.execute(
        select(Portfolio.current_cash).where(Portfolio.id == portfolio_id)
    )
    current_cash = portfolio_result.scalar_one()

    positions_sum_result = await db.execute(
        select(func.coalesce(func.sum(PortfolioPosition.entry_value_usd), 0)).where(
            PortfolioPosition.portfolio_id == portfolio_id,
            PortfolioPosition.status == "open",
        )
    )
    positions_value = positions_sum_result.scalar_one()
    current_equity = float(current_cash) + float(positions_value)

    # 3. Get or create day-open equity snapshot
    snapshot_result = await db.execute(
        select(ProtectionEvent).where(
            ProtectionEvent.protection_type == "daily_equity_snapshot",
            ProtectionEvent.triggered_at >= day_start,
            ProtectionEvent.triggered_at < day_end,
        ).limit(1)
    )
    snapshot = snapshot_result.scalars().first()

    if snapshot is None:
        snapshot = ProtectionEvent(
            protection_type="daily_equity_snapshot",
            status="expired",
            reason="Day-open equity snapshot",
            context_data={"day_open_equity": current_equity, "date": now.date().isoformat()},
            triggered_at=now,
            expires_at=day_end,
        )
        db.add(snapshot)
        await db.flush()

    day_open_equity = float(snapshot.context_data["day_open_equity"])  # type: ignore[index]

    # 4. Calculate drawdown
    if day_open_equity <= 0:
        return True, None, None

    dd_pct = ((day_open_equity - current_equity) / day_open_equity) * 100.0

    if dd_pct >= DAILY_DRAWDOWN_LIMIT_PCT:
        reason = (
            f"Equity dropped {dd_pct:.1f}% from day open "
            f"(${day_open_equity:.2f} -> ${current_equity:.2f})"
        )
        event = ProtectionEvent(
            protection_type="daily_drawdown",
            status="active",
            reason=reason,
            context_data={
                "day_open_equity": day_open_equity,
                "current_equity": current_equity,
                "drawdown_pct": round(dd_pct, 2),
            },
            triggered_at=now,
            expires_at=day_end,
        )
        db.add(event)
        await db.flush()
        log.info("portfolio.daily_drawdown_triggered", drawdown_pct=dd_pct, reason=reason)
        return False, "daily_drawdown", reason

    return True, None, None


# ── Helpers ───────────────────────────────────────

async def _expire_protections(db: AsyncSession, now: datetime) -> None:
    """Mark expired protections."""
    from sqlalchemy import update
    await db.execute(
        update(ProtectionEvent)
        .where(
            ProtectionEvent.status == "active",
            ProtectionEvent.expires_at.isnot(None),
            ProtectionEvent.expires_at <= now,
        )
        .values(status="expired")
    )


async def _log_protection(
    db: AsyncSession, ptype: str, reason: str,
    asset_id: uuid.UUID | None = None,
    asset_class: str | None = None,
    now: datetime | None = None,
    expires: datetime | None = None,
) -> None:
    # Don't create duplicate active protection of same type+asset
    conditions = [ProtectionEvent.protection_type == ptype, ProtectionEvent.status == "active"]
    if asset_id:
        conditions.append(ProtectionEvent.asset_id == asset_id)
    existing = await db.execute(select(func.count()).where(and_(*conditions)))
    if existing.scalar_one() > 0:
        return

    event = ProtectionEvent(
        protection_type=ptype,
        status="active",
        asset_id=asset_id,
        asset_class=asset_class,
        reason=reason,
        triggered_at=now or datetime.now(timezone.utc),
        expires_at=expires,
    )
    db.add(event)
    log.info("portfolio.protection_triggered", type=ptype, reason=reason)

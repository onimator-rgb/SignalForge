"""Rule-based exit manager — closes positions WITHOUT calling LLM.

Hard exits (stop-loss, take-profit, max-hold) don't need AI reasoning.
This runs BEFORE the LLM evaluation round, saving tokens and ensuring
fast reactions to price moves.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.service import get_latest_price
from app.logging_config import get_logger
from app.portfolio.models import Portfolio, PortfolioPosition, PortfolioTransaction

from .models import AITrader

log = get_logger(__name__)


async def check_hard_exits(db: AsyncSession) -> list[dict]:
    """Check all open positions for rule-based exits.

    Runs independently of LLM — pure price vs threshold checks.
    Returns list of closed positions.
    """
    closed = []

    traders_result = await db.execute(
        select(AITrader).where(AITrader.is_active.is_(True))
    )
    db_traders = traders_result.scalars().all()

    now = datetime.now(timezone.utc)

    for db_trader in db_traders:
        if not db_trader.portfolio_id:
            continue

        risk = db_trader.risk_params
        stop_loss_pct = risk.get("stop_loss_pct", -0.08)
        take_profit_pct = risk.get("take_profit_pct", 0.15)

        positions_result = await db.execute(
            select(PortfolioPosition).where(
                PortfolioPosition.portfolio_id == db_trader.portfolio_id,
                PortfolioPosition.status == "open",
            )
        )
        positions = positions_result.scalars().all()

        for pos in positions:
            price_data = await get_latest_price(db, pos.asset_id)
            if not price_data or not price_data.close:
                continue

            current_price = float(price_data.close)
            entry_price = float(pos.entry_price)
            pnl_pct = (current_price - entry_price) / entry_price

            close_reason = None

            # Stop-loss
            if pnl_pct <= stop_loss_pct:
                close_reason = f"stop_loss:{db_trader.slug}"

            # Take-profit
            elif pnl_pct >= take_profit_pct:
                close_reason = f"take_profit:{db_trader.slug}"

            # Explicit stop-loss price
            elif pos.stop_loss_price and current_price <= float(pos.stop_loss_price):
                close_reason = f"sl_price:{db_trader.slug}"

            # Explicit take-profit price
            elif pos.take_profit_price and current_price >= float(pos.take_profit_price):
                close_reason = f"tp_price:{db_trader.slug}"

            # Max hold time exceeded
            elif pos.max_hold_until and now >= pos.max_hold_until:
                close_reason = f"max_hold:{db_trader.slug}"

            if close_reason:
                result = await _close_position(db, db_trader, pos, current_price, close_reason, now)
                closed.append(result)

    if closed:
        await db.commit()
        log.info("exit_manager.hard_exits", count=len(closed))

    return closed


async def _close_position(
    db: AsyncSession,
    db_trader: AITrader,
    pos: PortfolioPosition,
    current_price: float,
    close_reason: str,
    now: datetime,
) -> dict:
    """Close a position and update portfolio."""
    portfolio = await db.get(Portfolio, db_trader.portfolio_id)

    exit_value = float(pos.quantity) * current_price
    realized_pnl = exit_value - float(pos.entry_value_usd)
    realized_pnl_pct = realized_pnl / float(pos.entry_value_usd) * 100

    pos.exit_price = current_price
    pos.exit_value_usd = exit_value
    pos.closed_at = now
    pos.close_reason = close_reason
    pos.realized_pnl_usd = realized_pnl
    pos.realized_pnl_pct = realized_pnl_pct
    pos.status = "closed"

    tx = PortfolioTransaction(
        portfolio_id=db_trader.portfolio_id,
        position_id=pos.id,
        tx_type="sell",
        asset_id=pos.asset_id,
        price=current_price,
        quantity=float(pos.quantity),
        value_usd=exit_value,
        executed_at=now,
    )
    db.add(tx)

    if portfolio:
        portfolio.current_cash = float(portfolio.current_cash) + exit_value

    if realized_pnl > 0:
        db_trader.win_count += 1
    else:
        db_trader.loss_count += 1

    await db.flush()

    log.info(
        "exit_manager.position_closed",
        trader=db_trader.slug,
        asset_id=str(pos.asset_id),
        reason=close_reason,
        pnl_pct=round(realized_pnl_pct, 2),
    )

    return {
        "trader": db_trader.slug,
        "asset_id": str(pos.asset_id),
        "reason": close_reason,
        "pnl_usd": round(realized_pnl, 2),
        "pnl_pct": round(realized_pnl_pct, 2),
    }

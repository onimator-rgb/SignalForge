"""Portfolio service — manages demo positions based on recommendations."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.assets.service import get_latest_price
from app.logging_config import get_logger
from app.portfolio.models import Portfolio, PortfolioPosition, PortfolioTransaction
from app.portfolio.rules import (
    ALLOWED_CONFIDENCE, BLOCKED_RISK, COOLDOWN_HOURS, INITIAL_CAPITAL,
    MAX_HOLD_HOURS, MAX_OPEN_POSITIONS, MAX_POSITION_PCT,
    MIN_CASH_RESERVE_PCT, MIN_POSITION_USD, MIN_SCORE_FOR_ENTRY,
    STOP_LOSS_PCT, TAKE_PROFIT_PCT,
)
from app.recommendations.models import Recommendation

log = get_logger(__name__)


async def get_or_create_portfolio(db: AsyncSession) -> Portfolio:
    """Get the default demo portfolio, creating it if needed."""
    result = await db.execute(
        select(Portfolio).where(Portfolio.is_active.is_(True)).limit(1)
    )
    portfolio = result.scalar_one_or_none()
    if not portfolio:
        portfolio = Portfolio(
            name="Demo Portfolio",
            initial_capital=INITIAL_CAPITAL,
            current_cash=INITIAL_CAPITAL,
        )
        db.add(portfolio)
        await db.flush()
        log.info("portfolio.created", id=str(portfolio.id), capital=INITIAL_CAPITAL)
    return portfolio


async def evaluate_portfolio(db: AsyncSession) -> dict:
    """Main portfolio cycle: check exits, then check entries. Returns summary."""
    portfolio = await get_or_create_portfolio(db)
    now = datetime.now(timezone.utc)

    closed = await _check_exits(db, portfolio, now)
    opened = await _check_entries(db, portfolio, now)

    await db.flush()
    portfolio.updated_at = now
    await db.commit()

    if closed or opened:
        log.info("portfolio.evaluate_done", closed=closed, opened=opened,
                 cash=float(portfolio.current_cash))
    return {"closed": closed, "opened": opened}


# ── Exit logic ────────────────────────────────────

async def _check_exits(db: AsyncSession, portfolio: Portfolio, now: datetime) -> int:
    """Check all open positions for exit conditions. Returns count closed."""
    result = await db.execute(
        select(PortfolioPosition).where(
            PortfolioPosition.portfolio_id == portfolio.id,
            PortfolioPosition.status == "open",
        )
    )
    positions = list(result.scalars().all())
    closed = 0

    for pos in positions:
        price_data = await get_latest_price(db, pos.asset_id)
        if not price_data:
            continue

        current_price = price_data.close
        pnl_pct = (current_price - float(pos.entry_price)) / float(pos.entry_price)
        reason = None

        # Priority: stop > target > max_hold
        if pnl_pct <= STOP_LOSS_PCT:
            reason = "stop_hit"
        elif pnl_pct >= TAKE_PROFIT_PCT:
            reason = "target_hit"
        elif pos.max_hold_until and now >= pos.max_hold_until:
            reason = "max_hold"

        if reason:
            await _close_position(db, portfolio, pos, current_price, reason, now)
            closed += 1

    return closed


async def _close_position(
    db: AsyncSession, portfolio: Portfolio, pos: PortfolioPosition,
    exit_price: float, reason: str, now: datetime,
) -> None:
    """Close a position and record the transaction."""
    qty = float(pos.quantity)
    exit_value = round(exit_price * qty, 2)
    entry_value = float(pos.entry_value_usd)
    pnl_usd = round(exit_value - entry_value, 2)
    pnl_pct = round((exit_price - float(pos.entry_price)) / float(pos.entry_price) * 100, 4)

    pos.exit_price = exit_price
    pos.exit_value_usd = exit_value
    pos.closed_at = now
    pos.close_reason = reason
    pos.realized_pnl_usd = pnl_usd
    pos.realized_pnl_pct = pnl_pct
    pos.status = "closed"

    portfolio.current_cash = float(portfolio.current_cash) + exit_value

    tx = PortfolioTransaction(
        portfolio_id=portfolio.id,
        position_id=pos.id,
        tx_type="sell",
        asset_id=pos.asset_id,
        price=exit_price,
        quantity=qty,
        value_usd=exit_value,
        executed_at=now,
    )
    db.add(tx)

    # Fetch symbol for logging
    asset_res = await db.execute(select(Asset.symbol).where(Asset.id == pos.asset_id))
    symbol = asset_res.scalar_one_or_none() or "?"

    log.info(
        "portfolio.position_closed",
        symbol=symbol, reason=reason,
        entry=float(pos.entry_price), exit=exit_price,
        pnl_usd=pnl_usd, pnl_pct=pnl_pct,
    )


# ── Entry logic ───────────────────────────────────

async def _check_entries(db: AsyncSession, portfolio: Portfolio, now: datetime) -> int:
    """Check active recommendations for entry opportunities. Returns count opened."""
    # Count open positions
    open_count_res = await db.execute(
        select(func.count()).where(
            PortfolioPosition.portfolio_id == portfolio.id,
            PortfolioPosition.status == "open",
        )
    )
    open_count = open_count_res.scalar_one()
    if open_count >= MAX_OPEN_POSITIONS:
        return 0

    # Get open asset IDs (can't open duplicate)
    open_assets_res = await db.execute(
        select(PortfolioPosition.asset_id).where(
            PortfolioPosition.portfolio_id == portfolio.id,
            PortfolioPosition.status == "open",
        )
    )
    open_asset_ids = set(r[0] for r in open_assets_res.all())

    # Get recently closed asset IDs (cooldown)
    cooldown_since = now - timedelta(hours=COOLDOWN_HOURS)
    cooldown_res = await db.execute(
        select(PortfolioPosition.asset_id).where(
            PortfolioPosition.portfolio_id == portfolio.id,
            PortfolioPosition.status == "closed",
            PortfolioPosition.closed_at >= cooldown_since,
        )
    )
    cooldown_asset_ids = set(r[0] for r in cooldown_res.all())

    blocked_ids = open_asset_ids | cooldown_asset_ids

    # Get eligible recommendations
    recs_res = await db.execute(
        select(Recommendation)
        .where(
            Recommendation.status == "active",
            Recommendation.recommendation_type == "candidate_buy",
            Recommendation.score >= MIN_SCORE_FOR_ENTRY,
            Recommendation.confidence.in_(ALLOWED_CONFIDENCE),
            ~Recommendation.risk_level.in_(BLOCKED_RISK),
        )
        .order_by(Recommendation.score.desc())
    )
    candidates = list(recs_res.scalars().all())

    opened = 0
    equity = await _compute_equity(db, portfolio)

    for rec in candidates:
        if rec.asset_id in blocked_ids:
            continue
        if open_count + opened >= MAX_OPEN_POSITIONS:
            break

        # Check cash reserve
        reserve = float(portfolio.initial_capital) * MIN_CASH_RESERVE_PCT
        available = float(portfolio.current_cash) - reserve
        if available < MIN_POSITION_USD:
            break

        # Position sizing
        max_size = equity * MAX_POSITION_PCT
        size_usd = min(max_size, available)
        if size_usd < MIN_POSITION_USD:
            break

        # Get current price
        price_data = await get_latest_price(db, rec.asset_id)
        if not price_data:
            continue

        price = price_data.close
        quantity = size_usd / price

        pos = PortfolioPosition(
            portfolio_id=portfolio.id,
            asset_id=rec.asset_id,
            recommendation_id=rec.id,
            entry_price=price,
            quantity=quantity,
            entry_value_usd=round(size_usd, 2),
            opened_at=now,
            stop_loss_price=round(price * (1 + STOP_LOSS_PCT), 8),
            take_profit_price=round(price * (1 + TAKE_PROFIT_PCT), 8),
            max_hold_until=now + timedelta(hours=MAX_HOLD_HOURS),
        )
        db.add(pos)
        await db.flush()

        tx = PortfolioTransaction(
            portfolio_id=portfolio.id,
            position_id=pos.id,
            tx_type="buy",
            asset_id=rec.asset_id,
            price=price,
            quantity=quantity,
            value_usd=round(size_usd, 2),
            executed_at=now,
        )
        db.add(tx)

        portfolio.current_cash = float(portfolio.current_cash) - round(size_usd, 2)
        blocked_ids.add(rec.asset_id)
        opened += 1

        asset_res = await db.execute(select(Asset.symbol).where(Asset.id == rec.asset_id))
        symbol = asset_res.scalar_one_or_none() or "?"

        log.info(
            "portfolio.position_opened",
            symbol=symbol, price=price,
            quantity=round(quantity, 8), value_usd=round(size_usd, 2),
            score=float(rec.score),
        )

    return opened


# ── Query helpers ─────────────────────────────────

async def _compute_equity(db: AsyncSession, portfolio: Portfolio) -> float:
    """Cash + current value of open positions."""
    result = await db.execute(
        select(PortfolioPosition).where(
            PortfolioPosition.portfolio_id == portfolio.id,
            PortfolioPosition.status == "open",
        )
    )
    positions = list(result.scalars().all())
    positions_value = 0.0
    for pos in positions:
        price_data = await get_latest_price(db, pos.asset_id)
        if price_data:
            positions_value += price_data.close * float(pos.quantity)
        else:
            positions_value += float(pos.entry_value_usd)
    return float(portfolio.current_cash) + positions_value


async def get_portfolio_summary(db: AsyncSession) -> dict:
    """Build full portfolio summary for the API."""
    portfolio = await get_or_create_portfolio(db)

    # Open positions with current prices
    open_res = await db.execute(
        select(PortfolioPosition, Asset.symbol, Asset.asset_class)
        .join(Asset, PortfolioPosition.asset_id == Asset.id)
        .where(
            PortfolioPosition.portfolio_id == portfolio.id,
            PortfolioPosition.status == "open",
        )
        .order_by(PortfolioPosition.opened_at.desc())
    )
    open_positions = []
    positions_value = 0.0
    for row in open_res.all():
        pos = row.PortfolioPosition
        price_data = await get_latest_price(db, pos.asset_id)
        current_price = price_data.close if price_data else float(pos.entry_price)
        current_value = current_price * float(pos.quantity)
        unrealized_pnl = round(current_value - float(pos.entry_value_usd), 2)
        unrealized_pct = round((current_price / float(pos.entry_price) - 1) * 100, 4) if float(pos.entry_price) > 0 else 0
        positions_value += current_value

        open_positions.append({
            "id": pos.id, "asset_id": pos.asset_id, "asset_symbol": row.symbol,
            "asset_class": row.asset_class, "recommendation_id": pos.recommendation_id,
            "entry_price": float(pos.entry_price), "quantity": float(pos.quantity),
            "entry_value_usd": float(pos.entry_value_usd), "opened_at": pos.opened_at,
            "exit_price": None, "exit_value_usd": None, "closed_at": None,
            "close_reason": None, "realized_pnl_usd": None, "realized_pnl_pct": None,
            "stop_loss_price": float(pos.stop_loss_price) if pos.stop_loss_price else None,
            "take_profit_price": float(pos.take_profit_price) if pos.take_profit_price else None,
            "max_hold_until": pos.max_hold_until, "status": pos.status,
            "current_price": current_price, "current_value_usd": round(current_value, 2),
            "unrealized_pnl_usd": unrealized_pnl, "unrealized_pnl_pct": unrealized_pct,
        })

    # Closed positions
    closed_res = await db.execute(
        select(PortfolioPosition, Asset.symbol, Asset.asset_class)
        .join(Asset, PortfolioPosition.asset_id == Asset.id)
        .where(
            PortfolioPosition.portfolio_id == portfolio.id,
            PortfolioPosition.status == "closed",
        )
        .order_by(PortfolioPosition.closed_at.desc())
        .limit(20)
    )
    closed_positions = []
    for row in closed_res.all():
        pos = row.PortfolioPosition
        closed_positions.append({
            "id": pos.id, "asset_id": pos.asset_id, "asset_symbol": row.symbol,
            "asset_class": row.asset_class, "recommendation_id": pos.recommendation_id,
            "entry_price": float(pos.entry_price), "quantity": float(pos.quantity),
            "entry_value_usd": float(pos.entry_value_usd), "opened_at": pos.opened_at,
            "exit_price": float(pos.exit_price) if pos.exit_price else None,
            "exit_value_usd": float(pos.exit_value_usd) if pos.exit_value_usd else None,
            "closed_at": pos.closed_at, "close_reason": pos.close_reason,
            "realized_pnl_usd": float(pos.realized_pnl_usd) if pos.realized_pnl_usd else None,
            "realized_pnl_pct": float(pos.realized_pnl_pct) if pos.realized_pnl_pct else None,
            "stop_loss_price": None, "take_profit_price": None,
            "max_hold_until": None, "status": pos.status,
            "current_price": None, "current_value_usd": None,
            "unrealized_pnl_usd": None, "unrealized_pnl_pct": None,
        })

    # Transactions
    tx_res = await db.execute(
        select(PortfolioTransaction, Asset.symbol)
        .join(Asset, PortfolioTransaction.asset_id == Asset.id)
        .where(PortfolioTransaction.portfolio_id == portfolio.id)
        .order_by(PortfolioTransaction.executed_at.desc())
        .limit(20)
    )
    transactions = [
        {
            "id": row.PortfolioTransaction.id, "tx_type": row.PortfolioTransaction.tx_type,
            "asset_id": row.PortfolioTransaction.asset_id, "asset_symbol": row.symbol,
            "price": float(row.PortfolioTransaction.price),
            "quantity": float(row.PortfolioTransaction.quantity),
            "value_usd": float(row.PortfolioTransaction.value_usd),
            "executed_at": row.PortfolioTransaction.executed_at,
        }
        for row in tx_res.all()
    ]

    # Stats
    cash = float(portfolio.current_cash)
    equity = cash + positions_value
    total_return_pct = round((equity / float(portfolio.initial_capital) - 1) * 100, 2)

    all_closed_res = await db.execute(
        select(PortfolioPosition).where(
            PortfolioPosition.portfolio_id == portfolio.id,
            PortfolioPosition.status == "closed",
        )
    )
    all_closed = list(all_closed_res.scalars().all())
    wins = [p for p in all_closed if p.realized_pnl_usd and float(p.realized_pnl_usd) > 0]
    pnl_pcts = [float(p.realized_pnl_pct) for p in all_closed if p.realized_pnl_pct is not None]
    total_realized = sum(float(p.realized_pnl_usd) for p in all_closed if p.realized_pnl_usd)

    return {
        "stats": {
            "initial_capital": float(portfolio.initial_capital),
            "current_cash": cash,
            "equity": round(equity, 2),
            "total_return_pct": total_return_pct,
            "open_positions": len(open_positions),
            "closed_positions": len(all_closed),
            "total_trades": len(all_closed) + len(open_positions),
            "win_rate": round(len(wins) / len(all_closed) * 100, 1) if all_closed else None,
            "avg_return_pct": round(sum(pnl_pcts) / len(pnl_pcts), 2) if pnl_pcts else None,
            "best_trade_pct": round(max(pnl_pcts), 2) if pnl_pcts else None,
            "worst_trade_pct": round(min(pnl_pcts), 2) if pnl_pcts else None,
            "total_realized_pnl": round(total_realized, 2),
        },
        "open_positions": open_positions,
        "recent_closed": closed_positions,
        "recent_transactions": transactions,
    }

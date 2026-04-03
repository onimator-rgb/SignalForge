"""AI Trader Arena — orchestrates autonomous traders, executes trades, tracks performance.

The Arena:
1. Initializes each AI trader with its own portfolio
2. Periodically evaluates all active assets for each trader
3. Executes buy/sell decisions as paper trades
4. Takes daily snapshots for performance comparison
5. Provides leaderboard data
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.assets.service import get_latest_price
from app.logging_config import get_logger
from app.portfolio.models import Portfolio, PortfolioPosition, PortfolioTransaction

from .base import BaseAITrader, TradeAction, TradeDecision
from .context import build_asset_context
from .exit_manager import check_hard_exits
from .models import AITrader, AITraderDecision, AITraderSnapshot
from .pre_filter import apply_pre_filter
from .registry import get_all_traders

log = get_logger(__name__)

# Arena constants
INITIAL_CAPITAL = 10_000.00
MIN_TRADE_VALUE_USD = 10.00


async def initialize_arena(db: AsyncSession) -> list[dict]:
    """Create DB records and portfolios for all AI traders (idempotent)."""
    traders = get_all_traders()
    results = []

    for trader in traders:
        # Check if already exists
        existing = await db.execute(
            select(AITrader).where(AITrader.slug == trader.slug)
        )
        ai_trader = existing.scalar_one_or_none()

        if ai_trader:
            results.append({"slug": trader.slug, "status": "exists", "id": str(ai_trader.id)})
            continue

        # Create dedicated portfolio
        portfolio = Portfolio(
            name=f"AI: {trader.name}",
            initial_capital=INITIAL_CAPITAL,
            current_cash=INITIAL_CAPITAL,
        )
        db.add(portfolio)
        await db.flush()

        # Create trader record
        ai_trader = AITrader(
            name=trader.name,
            slug=trader.slug,
            description=f"{trader.name} — autonomous AI trading agent",
            personality=trader.get_system_prompt()[:500],  # truncate for DB
            llm_provider=trader.llm_provider,
            llm_model=trader.llm_model,
            strategy_config={"risk_params": trader.risk_params},
            risk_params=trader.risk_params,
            portfolio_id=portfolio.id,
        )
        db.add(ai_trader)
        await db.flush()

        results.append({"slug": trader.slug, "status": "created", "id": str(ai_trader.id)})
        log.info("arena.trader_created", name=trader.name, slug=trader.slug)

    await db.commit()
    return results


async def run_evaluation_round(db: AsyncSession) -> dict:
    """Run one evaluation round: all traders analyze all active assets.

    Returns summary of decisions and executions.
    """
    # Get active traders
    traders_result = await db.execute(
        select(AITrader).where(AITrader.is_active.is_(True))
    )
    db_traders = traders_result.scalars().all()

    if not db_traders:
        return {"error": "No active traders. Run initialize_arena first."}

    # Get active assets
    assets_result = await db.execute(
        select(Asset).where(Asset.is_active.is_(True))
    )
    assets = assets_result.scalars().all()

    if not assets:
        return {"error": "No active assets."}

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "traders_evaluated": 0,
        "assets_evaluated": 0,
        "pre_filtered": 0,
        "llm_calls": 0,
        "decisions_made": 0,
        "trades_executed": 0,
        "hard_exits": 0,
        "decisions": [],
    }

    # Phase 1: Rule-based hard exits (no LLM needed)
    hard_exits = await check_hard_exits(db)
    summary["hard_exits"] = len(hard_exits)

    # Phase 2: LLM-driven analysis (with pre-filtering)
    trader_instances = {t.slug: t for t in get_all_traders()}

    for db_trader in db_traders:
        trader = trader_instances.get(db_trader.slug)
        if not trader:
            continue

        summary["traders_evaluated"] += 1

        for asset in assets:
            summary["assets_evaluated"] += 1

            # Build context
            ctx = await build_asset_context(db, asset.id, db_trader.portfolio_id)

            if ctx.get("error") or not ctx.get("price", {}).get("current"):
                continue

            # Pre-filter: skip obvious non-trades WITHOUT calling LLM
            filter_result = apply_pre_filter(db_trader.slug, ctx)
            if not filter_result.should_analyze:
                summary["pre_filtered"] += 1
                continue

            # Get AI decision (LLM call) — small delay to respect rate limits
            summary["llm_calls"] += 1
            await asyncio.sleep(0.5)
            decision = await trader.decide(ctx)

            # Save decision to DB
            db_decision = AITraderDecision(
                trader_id=db_trader.id,
                asset_id=asset.id,
                action=decision.action.value,
                confidence=decision.confidence,
                reasoning=decision.reasoning,
                market_context=ctx.get("price", {}),
                indicators_snapshot=ctx.get("indicators", {}),
                position_size_pct=decision.position_size_pct,
                target_entry_price=decision.target_entry_price,
                stop_loss_price=decision.stop_loss_price,
                take_profit_price=decision.take_profit_price,
                llm_model_used=decision.model_used,
                llm_cost_usd=decision.cost_usd,
                latency_ms=decision.latency_ms,
            )
            db.add(db_decision)
            summary["decisions_made"] += 1

            # Execute trade if actionable
            executed = False
            if decision.action == TradeAction.BUY and decision.confidence >= 0.5:
                executed = await _execute_buy(
                    db, db_trader, asset, decision, ctx
                )
            elif decision.action == TradeAction.SELL and decision.confidence >= 0.4:
                executed = await _execute_sell(
                    db, db_trader, asset, decision, ctx
                )

            if executed:
                db_decision.executed = True
                summary["trades_executed"] += 1

            summary["decisions"].append({
                "trader": db_trader.slug,
                "asset": asset.symbol,
                "action": decision.action.value,
                "confidence": decision.confidence,
                "executed": executed,
            })

        # Update trader stats
        db_trader.total_decisions += summary["decisions_made"]

    await db.commit()

    log.info(
        "arena.round_complete",
        traders=summary["traders_evaluated"],
        assets=summary["assets_evaluated"],
        decisions=summary["decisions_made"],
        executed=summary["trades_executed"],
    )

    return summary


async def _execute_buy(
    db: AsyncSession,
    db_trader: AITrader,
    asset: Asset,
    decision: TradeDecision,
    ctx: dict,
) -> bool:
    """Execute a buy order for the AI trader."""
    if not db_trader.portfolio_id:
        return False

    portfolio = await db.get(Portfolio, db_trader.portfolio_id)
    if not portfolio:
        return False

    current_price = ctx["price"]["current"]
    if not current_price or current_price <= 0:
        return False

    # Check cash and position limits
    max_positions = decision.position_size_pct or 0.15
    position_value = float(portfolio.current_cash) * max_positions
    position_value = min(position_value, float(portfolio.current_cash) * 0.90)  # keep 10% min

    if position_value < MIN_TRADE_VALUE_USD:
        return False

    # Check max open positions from risk params
    max_open = db_trader.risk_params.get("max_open_positions", 5)
    count_result = await db.execute(
        select(func.count()).where(
            PortfolioPosition.portfolio_id == db_trader.portfolio_id,
            PortfolioPosition.status == "open",
        )
    )
    open_count = count_result.scalar_one()
    if open_count >= max_open:
        return False

    # Check if already holding this asset
    existing = await db.execute(
        select(PortfolioPosition).where(
            PortfolioPosition.portfolio_id == db_trader.portfolio_id,
            PortfolioPosition.asset_id == asset.id,
            PortfolioPosition.status == "open",
        )
    )
    if existing.scalar_one_or_none():
        return False

    # Execute
    quantity = position_value / current_price
    now = datetime.now(timezone.utc)

    position = PortfolioPosition(
        portfolio_id=db_trader.portfolio_id,
        asset_id=asset.id,
        entry_price=current_price,
        quantity=quantity,
        entry_value_usd=position_value,
        opened_at=now,
        stop_loss_price=decision.stop_loss_price,
        take_profit_price=decision.take_profit_price,
        max_hold_until=now + timedelta(hours=72),
        status="open",
    )
    db.add(position)

    tx = PortfolioTransaction(
        portfolio_id=db_trader.portfolio_id,
        position_id=position.id,
        tx_type="buy",
        asset_id=asset.id,
        price=current_price,
        quantity=quantity,
        value_usd=position_value,
        executed_at=now,
    )
    db.add(tx)

    portfolio.current_cash = float(portfolio.current_cash) - position_value
    await db.flush()

    log.info(
        "arena.buy_executed",
        trader=db_trader.slug,
        asset=asset.symbol,
        price=current_price,
        value_usd=round(position_value, 2),
        confidence=decision.confidence,
    )
    return True


async def _execute_sell(
    db: AsyncSession,
    db_trader: AITrader,
    asset: Asset,
    decision: TradeDecision,
    ctx: dict,
) -> bool:
    """Execute a sell (close position) for the AI trader."""
    if not db_trader.portfolio_id:
        return False

    # Find open position
    result = await db.execute(
        select(PortfolioPosition).where(
            PortfolioPosition.portfolio_id == db_trader.portfolio_id,
            PortfolioPosition.asset_id == asset.id,
            PortfolioPosition.status == "open",
        )
    )
    position = result.scalar_one_or_none()
    if not position:
        return False

    current_price = ctx["price"]["current"]
    if not current_price or current_price <= 0:
        return False

    portfolio = await db.get(Portfolio, db_trader.portfolio_id)
    if not portfolio:
        return False

    now = datetime.now(timezone.utc)
    exit_value = float(position.quantity) * current_price
    realized_pnl = exit_value - float(position.entry_value_usd)
    realized_pnl_pct = realized_pnl / float(position.entry_value_usd) * 100

    # Close position
    position.exit_price = current_price
    position.exit_value_usd = exit_value
    position.closed_at = now
    position.close_reason = f"ai_sell:{db_trader.slug}"
    position.realized_pnl_usd = realized_pnl
    position.realized_pnl_pct = realized_pnl_pct
    position.status = "closed"

    tx = PortfolioTransaction(
        portfolio_id=db_trader.portfolio_id,
        position_id=position.id,
        tx_type="sell",
        asset_id=asset.id,
        price=current_price,
        quantity=float(position.quantity),
        value_usd=exit_value,
        executed_at=now,
    )
    db.add(tx)

    portfolio.current_cash = float(portfolio.current_cash) + exit_value

    # Update win/loss counters
    if realized_pnl > 0:
        db_trader.win_count += 1
    else:
        db_trader.loss_count += 1

    await db.flush()

    log.info(
        "arena.sell_executed",
        trader=db_trader.slug,
        asset=asset.symbol,
        pnl_usd=round(realized_pnl, 2),
        pnl_pct=round(realized_pnl_pct, 2),
    )
    return True


async def take_daily_snapshots(db: AsyncSession) -> list[dict]:
    """Capture performance snapshot for each trader (call once per day)."""
    today = date.today()

    traders_result = await db.execute(
        select(AITrader).where(AITrader.is_active.is_(True))
    )
    db_traders = traders_result.scalars().all()

    snapshots = []

    for db_trader in db_traders:
        if not db_trader.portfolio_id:
            continue

        # Check if already snapped today
        existing = await db.execute(
            select(AITraderSnapshot).where(
                AITraderSnapshot.trader_id == db_trader.id,
                AITraderSnapshot.snapshot_date == today,
            )
        )
        if existing.scalar_one_or_none():
            continue

        portfolio = await db.get(Portfolio, db_trader.portfolio_id)
        if not portfolio:
            continue

        # Calculate portfolio value (cash + open positions at current prices)
        total_value = float(portfolio.current_cash)
        positions_result = await db.execute(
            select(PortfolioPosition).where(
                PortfolioPosition.portfolio_id == db_trader.portfolio_id,
                PortfolioPosition.status == "open",
            )
        )
        open_positions = positions_result.scalars().all()

        for pos in open_positions:
            price_data = await get_latest_price(db, pos.asset_id)
            if price_data and price_data.close:
                total_value += float(pos.quantity) * float(price_data.close)
            else:
                total_value += float(pos.entry_value_usd)

        initial = float(portfolio.initial_capital)
        total_return_pct = (total_value - initial) / initial * 100 if initial > 0 else 0

        # Count trades
        closed_result = await db.execute(
            select(func.count()).where(
                PortfolioPosition.portfolio_id == db_trader.portfolio_id,
                PortfolioPosition.status == "closed",
            )
        )
        total_trades = closed_result.scalar_one()

        # Win rate
        win_rate = None
        if total_trades > 0:
            win_rate = db_trader.win_count / total_trades

        # Get previous snapshot for daily return
        prev_result = await db.execute(
            select(AITraderSnapshot)
            .where(
                AITraderSnapshot.trader_id == db_trader.id,
                AITraderSnapshot.snapshot_date < today,
            )
            .order_by(AITraderSnapshot.snapshot_date.desc())
            .limit(1)
        )
        prev = prev_result.scalar_one_or_none()
        daily_return_pct = None
        if prev and float(prev.portfolio_value_usd) > 0:
            daily_return_pct = (total_value - float(prev.portfolio_value_usd)) / float(prev.portfolio_value_usd) * 100

        snapshot = AITraderSnapshot(
            trader_id=db_trader.id,
            snapshot_date=today,
            portfolio_value_usd=total_value,
            cash_usd=float(portfolio.current_cash),
            open_positions=len(open_positions),
            total_return_pct=total_return_pct,
            daily_return_pct=daily_return_pct,
            win_rate=win_rate,
            total_trades=total_trades,
        )
        db.add(snapshot)

        snapshots.append({
            "trader": db_trader.slug,
            "portfolio_value": round(total_value, 2),
            "total_return_pct": round(total_return_pct, 2),
            "daily_return_pct": round(daily_return_pct, 2) if daily_return_pct else None,
            "open_positions": len(open_positions),
            "total_trades": total_trades,
        })

    await db.commit()
    return snapshots


async def get_leaderboard(db: AsyncSession) -> list[dict]:
    """Get current leaderboard — all traders ranked by total return."""
    traders_result = await db.execute(
        select(AITrader).where(AITrader.is_active.is_(True))
    )
    db_traders = traders_result.scalars().all()

    leaderboard = []

    for db_trader in db_traders:
        if not db_trader.portfolio_id:
            continue

        portfolio = await db.get(Portfolio, db_trader.portfolio_id)
        if not portfolio:
            continue

        # Current value
        total_value = float(portfolio.current_cash)
        positions_result = await db.execute(
            select(PortfolioPosition).where(
                PortfolioPosition.portfolio_id == db_trader.portfolio_id,
                PortfolioPosition.status == "open",
            )
        )
        open_positions = positions_result.scalars().all()

        for pos in open_positions:
            price_data = await get_latest_price(db, pos.asset_id)
            if price_data and price_data.close:
                total_value += float(pos.quantity) * float(price_data.close)
            else:
                total_value += float(pos.entry_value_usd)

        initial = float(portfolio.initial_capital)
        total_return_pct = (total_value - initial) / initial * 100 if initial > 0 else 0

        total_trades = db_trader.win_count + db_trader.loss_count
        win_rate = (db_trader.win_count / total_trades * 100) if total_trades > 0 else 0

        leaderboard.append({
            "rank": 0,  # filled below
            "trader_id": str(db_trader.id),
            "name": db_trader.name,
            "slug": db_trader.slug,
            "llm_provider": db_trader.llm_provider,
            "llm_model": db_trader.llm_model,
            "portfolio_value_usd": round(total_value, 2),
            "initial_capital": initial,
            "total_return_pct": round(total_return_pct, 2),
            "total_decisions": db_trader.total_decisions,
            "total_trades": total_trades,
            "wins": db_trader.win_count,
            "losses": db_trader.loss_count,
            "win_rate_pct": round(win_rate, 1),
            "open_positions": len(open_positions),
            "cash_available": round(float(portfolio.current_cash), 2),
        })

    # Sort by total return descending
    leaderboard.sort(key=lambda x: x["total_return_pct"], reverse=True)
    for i, entry in enumerate(leaderboard):
        entry["rank"] = i + 1

    return leaderboard

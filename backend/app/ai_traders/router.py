"""REST API for AI Trader Arena."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

from .arena import (
    get_leaderboard,
    initialize_arena,
    run_evaluation_round,
    take_daily_snapshots,
)
from .exit_manager import check_hard_exits
from .models import AITrader, AITraderDecision, AITraderSnapshot
from .registry import TRADER_DESCRIPTIONS

router = APIRouter(prefix="/arena", tags=["arena"])


@router.post("/initialize")
async def api_initialize_arena(db: AsyncSession = Depends(get_db)) -> list[dict]:
    """Initialize all AI traders with their portfolios (idempotent)."""
    return await initialize_arena(db)


@router.post("/evaluate")
async def api_run_evaluation(db: AsyncSession = Depends(get_db)) -> dict:
    """Run one evaluation round — all traders analyze all assets."""
    return await run_evaluation_round(db)


@router.post("/check-exits")
async def api_check_exits(db: AsyncSession = Depends(get_db)) -> list[dict]:
    """Check and execute rule-based exits (stop-loss, take-profit, max-hold). No LLM needed."""
    return await check_hard_exits(db)


@router.post("/snapshots")
async def api_take_snapshots(db: AsyncSession = Depends(get_db)) -> list[dict]:
    """Take daily performance snapshots for all traders."""
    return await take_daily_snapshots(db)


@router.get("/leaderboard")
async def api_leaderboard(db: AsyncSession = Depends(get_db)) -> list[dict]:
    """Get current leaderboard ranked by total return."""
    return await get_leaderboard(db)


@router.get("/traders")
async def api_list_traders(db: AsyncSession = Depends(get_db)) -> list[dict]:
    """List all AI traders with their current status."""
    result = await db.execute(select(AITrader))
    traders = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "name": t.name,
            "slug": t.slug,
            "llm_provider": t.llm_provider,
            "llm_model": t.llm_model,
            "is_active": t.is_active,
            "total_decisions": t.total_decisions,
            "wins": t.win_count,
            "losses": t.loss_count,
            "description": TRADER_DESCRIPTIONS.get(t.slug, {}),
        }
        for t in traders
    ]


@router.get("/traders/{slug}/decisions")
async def api_trader_decisions(
    slug: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get recent decisions for a specific trader."""
    trader_result = await db.execute(
        select(AITrader).where(AITrader.slug == slug)
    )
    trader = trader_result.scalar_one_or_none()
    if not trader:
        return []

    result = await db.execute(
        select(AITraderDecision)
        .where(AITraderDecision.trader_id == trader.id)
        .order_by(AITraderDecision.created_at.desc())
        .limit(limit)
    )
    decisions = result.scalars().all()

    return [
        {
            "id": str(d.id),
            "created_at": d.created_at.isoformat(),
            "asset_id": str(d.asset_id),
            "action": d.action,
            "confidence": float(d.confidence),
            "reasoning": d.reasoning,
            "position_size_pct": float(d.position_size_pct) if d.position_size_pct else None,
            "stop_loss_price": float(d.stop_loss_price) if d.stop_loss_price else None,
            "take_profit_price": float(d.take_profit_price) if d.take_profit_price else None,
            "executed": d.executed,
            "llm_model_used": d.llm_model_used,
            "latency_ms": d.latency_ms,
        }
        for d in decisions
    ]


@router.get("/traders/{slug}/performance")
async def api_trader_performance(
    slug: str,
    days: int = 30,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get performance history (daily snapshots) for a trader."""
    trader_result = await db.execute(
        select(AITrader).where(AITrader.slug == slug)
    )
    trader = trader_result.scalar_one_or_none()
    if not trader:
        return []

    result = await db.execute(
        select(AITraderSnapshot)
        .where(AITraderSnapshot.trader_id == trader.id)
        .order_by(AITraderSnapshot.snapshot_date.desc())
        .limit(days)
    )
    snapshots = result.scalars().all()

    return [
        {
            "date": s.snapshot_date.isoformat(),
            "portfolio_value_usd": float(s.portfolio_value_usd),
            "cash_usd": float(s.cash_usd),
            "open_positions": s.open_positions,
            "total_return_pct": float(s.total_return_pct),
            "daily_return_pct": float(s.daily_return_pct) if s.daily_return_pct else None,
            "win_rate": float(s.win_rate) if s.win_rate else None,
            "total_trades": s.total_trades,
        }
        for s in snapshots
    ]


@router.get("/comparison")
async def api_comparison(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Compare all traders side-by-side over a time period."""
    leaderboard = await get_leaderboard(db)

    # Get equity curves for all traders
    traders_result = await db.execute(
        select(AITrader).where(AITrader.is_active.is_(True))
    )
    db_traders = traders_result.scalars().all()

    equity_curves = {}
    for trader in db_traders:
        result = await db.execute(
            select(AITraderSnapshot)
            .where(AITraderSnapshot.trader_id == trader.id)
            .order_by(AITraderSnapshot.snapshot_date.asc())
            .limit(days)
        )
        snapshots = result.scalars().all()
        equity_curves[trader.slug] = [
            {
                "date": s.snapshot_date.isoformat(),
                "value": float(s.portfolio_value_usd),
                "return_pct": float(s.total_return_pct),
            }
            for s in snapshots
        ]

    return {
        "leaderboard": leaderboard,
        "equity_curves": equity_curves,
        "period_days": days,
    }

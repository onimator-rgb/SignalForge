"""Backtest API router (marketpulse-task-2026-04-01-0001)."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.backtest.engine import backtest_metrics, simulate_trades
from app.backtest.schemas import BacktestRequest, BacktestResponse, TradeOut
from app.database import get_db
from app.market_data.models import PriceBar
from app.strategy.profiles import PROFILES

router = APIRouter(prefix="/api/v1/backtest", tags=["backtest"])


@router.post("/run", response_model=BacktestResponse)
async def run_backtest(
    req: BacktestRequest,
    db: AsyncSession = Depends(get_db),
) -> BacktestResponse:
    """Run a backtest on historical price data for a given asset."""
    # Validate profile
    profile = PROFILES.get(req.profile_name)
    if profile is None:
        raise HTTPException(status_code=400, detail="Unknown profile")

    # Load price bars
    cutoff = datetime.now(timezone.utc) - timedelta(days=req.lookback_days)
    stmt = (
        select(PriceBar.close)
        .where(
            PriceBar.asset_id == req.asset_id,
            PriceBar.interval == req.interval,
            PriceBar.time >= cutoff,
        )
        .order_by(PriceBar.time.asc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    if len(rows) < 2:
        raise HTTPException(status_code=404, detail="Not enough price data")

    prices = [float(r.close) for r in rows]

    # Run backtest
    trades = simulate_trades(prices, profile)
    metrics = backtest_metrics(trades)

    trade_list = [
        TradeOut(
            entry_index=t.entry_index,
            exit_index=t.exit_index,
            entry_price=t.entry_price,
            exit_price=t.exit_price,
            side=t.side,
            quantity=t.quantity,
            pnl=t.pnl,
            pnl_pct=t.pnl_pct,
            exit_reason=t.exit_reason,
        )
        for t in trades
    ]

    return BacktestResponse(
        total_return=metrics.total_return,
        total_return_pct=metrics.total_return_pct,
        max_drawdown_pct=metrics.max_drawdown_pct,
        sharpe_ratio=metrics.sharpe_ratio,
        win_rate=metrics.win_rate,
        profit_factor=metrics.profit_factor,
        total_trades=metrics.total_trades,
        avg_trade_pnl_pct=metrics.avg_trade_pnl_pct,
        best_trade_pnl_pct=metrics.best_trade_pnl_pct,
        worst_trade_pnl_pct=metrics.worst_trade_pnl_pct,
        trades=trade_list,
    )

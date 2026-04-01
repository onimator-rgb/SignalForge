"""AI Assistant API — portfolio report and strategy suggestions endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.logging_config import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


@router.get("/portfolio-report")
async def portfolio_report(db: AsyncSession = Depends(get_db)) -> dict:
    """Generate a plain-text portfolio analysis report."""
    from app.ai_assistant.portfolio_report import (
        PositionSummary,
        RiskSnapshot,
        TradeSummary,
        generate_portfolio_report,
    )
    from app.assets.models import Asset
    from app.portfolio.models import Portfolio, PortfolioPosition, PortfolioTransaction

    # Load portfolio
    result = await db.execute(
        select(Portfolio).where(Portfolio.is_active.is_(True)).limit(1)
    )
    portfolio = result.scalar_one_or_none()

    if portfolio is None:
        # No portfolio yet — return minimal report
        report = generate_portfolio_report(
            positions=[],
            risk=RiskSnapshot(
                sharpe_ratio=None,
                sortino_ratio=None,
                max_drawdown_pct=0.0,
                profit_factor=None,
                win_rate=None,
                total_closed=0,
                wins=0,
                losses=0,
                avg_hold_hours=0.0,
            ),
            recent_trades=[],
            regime="neutral",
            current_cash=0.0,
            initial_capital=0.0,
        )
        return {"report": report}

    # Load positions with asset symbols
    pos_rows = await db.execute(
        select(PortfolioPosition, Asset.symbol)
        .join(Asset, PortfolioPosition.asset_id == Asset.id)
        .where(PortfolioPosition.portfolio_id == portfolio.id)
    )
    positions: list[PositionSummary] = []
    open_count = 0
    closed_positions_data: list[PortfolioPosition] = []
    for row in pos_rows.all():
        pos = row.PortfolioPosition
        symbol = row.symbol
        unrealized_pnl_pct: float | None = None
        if pos.status == "open" and pos.entry_price and pos.entry_price > 0:
            # Use peak_price as proxy for current price if available
            current = float(pos.peak_price) if pos.peak_price else float(pos.entry_price)
            unrealized_pnl_pct = (current - float(pos.entry_price)) / float(pos.entry_price) * 100
        if pos.status == "open":
            open_count += 1
        else:
            closed_positions_data.append(pos)
        positions.append(
            PositionSummary(
                symbol=symbol,
                entry_price=float(pos.entry_price),
                current_price=float(pos.peak_price) if pos.peak_price else None,
                quantity=float(pos.quantity),
                unrealized_pnl_pct=unrealized_pnl_pct,
                status=pos.status,
                close_reason=pos.close_reason,
                realized_pnl_pct=float(pos.realized_pnl_pct) if pos.realized_pnl_pct is not None else None,
            )
        )

    # Build RiskSnapshot from closed positions
    wins = sum(1 for p in closed_positions_data if p.realized_pnl_pct is not None and float(p.realized_pnl_pct) > 0)
    losses = sum(1 for p in closed_positions_data if p.realized_pnl_pct is not None and float(p.realized_pnl_pct) <= 0)
    total_closed = len(closed_positions_data)
    win_rate = (wins / total_closed * 100) if total_closed > 0 else None
    realized_pcts = [float(p.realized_pnl_pct) for p in closed_positions_data if p.realized_pnl_pct is not None]
    best_trade = max(realized_pcts) if realized_pcts else None
    worst_trade = min(realized_pcts) if realized_pcts else None

    risk = RiskSnapshot(
        sharpe_ratio=None,
        sortino_ratio=None,
        max_drawdown_pct=abs(worst_trade) if worst_trade and worst_trade < 0 else 0.0,
        profit_factor=None,
        win_rate=win_rate,
        total_closed=total_closed,
        wins=wins,
        losses=losses,
        avg_hold_hours=0.0,
        best_trade_pct=best_trade,
        worst_trade_pct=worst_trade,
    )

    # Load recent transactions
    tx_rows = await db.execute(
        select(PortfolioTransaction, Asset.symbol)
        .join(Asset, PortfolioTransaction.asset_id == Asset.id)
        .where(PortfolioTransaction.portfolio_id == portfolio.id)
        .order_by(PortfolioTransaction.executed_at.desc())
        .limit(5)
    )
    recent_trades: list[TradeSummary] = []
    for tx_row in tx_rows.all():
        tx = tx_row.PortfolioTransaction
        recent_trades.append(
            TradeSummary(
                symbol=tx_row.symbol,
                action=tx.tx_type,
                price=float(tx.price),
                quantity=float(tx.quantity),
                value_usd=float(tx.value_usd),
            )
        )

    # Get market regime
    regime = "neutral"
    try:
        from app.strategy.regime import calculate_regime

        regime_data = await calculate_regime(db)
        regime = regime_data.get("regime", "neutral")
    except Exception:
        log.warning("ai.regime_unavailable", fallback="neutral")

    report = generate_portfolio_report(
        positions=positions,
        risk=risk,
        recent_trades=recent_trades,
        regime=regime,
        current_cash=float(portfolio.current_cash),
        initial_capital=float(portfolio.initial_capital),
    )

    log.info("ai.portfolio_report_generated", positions=len(positions), regime=regime)
    return {"report": report}


@router.get("/strategy-suggestions/{strategy_id}")
async def strategy_suggestions(
    strategy_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return improvement suggestions for a strategy.

    Since Strategy CRUD is not yet merged, this endpoint returns an empty
    suggestions list with a message indicating the feature is pending.
    """
    log.info("ai.strategy_suggestions_requested", strategy_id=strategy_id)
    return {
        "suggestions": [],
        "strategy_id": strategy_id,
        "message": "Strategy CRUD not yet available — suggestions will be enabled once strategy management endpoints are merged.",
    }

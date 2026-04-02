"""Portfolio endpoints — summary, positions, transactions, manual close."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.portfolio.service import evaluate_portfolio, get_portfolio_summary, manual_close_position

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])


@router.get("")
async def portfolio_summary(db: AsyncSession = Depends(get_db)):
    """Get full demo portfolio: stats, positions, transactions."""
    return await get_portfolio_summary(db)


@router.post("/evaluate")
async def trigger_evaluation(db: AsyncSession = Depends(get_db)):
    """Manually trigger portfolio evaluation (check entries/exits)."""
    result = await evaluate_portfolio(db)
    return {"status": "ok", **result}


@router.get("/entry-decisions")
async def entry_decisions(
    status: str | None = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Recent entry decisions (allowed/blocked) with reasons."""
    from sqlalchemy import select
    from app.portfolio.models import EntryDecision
    from app.assets.models import Asset

    q = (
        select(EntryDecision, Asset.symbol, Asset.asset_class)
        .join(Asset, EntryDecision.asset_id == Asset.id)
    )
    if status:
        q = q.where(EntryDecision.status == status)
    q = q.order_by(EntryDecision.created_at.desc()).limit(limit)

    result = await db.execute(q)
    rows = []
    for d in result.all():
        ctx = d.EntryDecision.context_data or {}
        rows.append({
            "id": str(d.EntryDecision.id),
            "symbol": d.symbol,
            "asset_class": d.asset_class,
            "status": d.EntryDecision.status,
            "stage": d.EntryDecision.stage,
            "reason_codes": d.EntryDecision.reason_codes,
            "reason_text": d.EntryDecision.reason_text,
            "regime": d.EntryDecision.regime,
            "profile": d.EntryDecision.profile,
            "created_at": d.EntryDecision.created_at.isoformat(),
            "context_data": ctx,
            "ranking_score": ctx.get("ranking_score"),
            "allocation_multiplier": ctx.get("allocation_multiplier"),
        })
    return rows


@router.get("/protections")
async def portfolio_protections(db: AsyncSession = Depends(get_db)):
    """Get active portfolio protection events."""
    from app.portfolio.protections import get_active_protections
    from app.portfolio.service import get_or_create_portfolio
    portfolio = await get_or_create_portfolio(db)
    protections = await get_active_protections(db, portfolio.id)
    return {"active": protections, "count": len(protections)}


@router.get("/risk-metrics")
async def risk_metrics(db: AsyncSession = Depends(get_db)):
    """Compute risk-adjusted performance metrics from closed positions."""
    from sqlalchemy import select
    from app.portfolio.models import PortfolioPosition
    from app.portfolio.risk_metrics import compute_risk_metrics
    from app.portfolio.schemas import RiskMetricsOut

    q = select(PortfolioPosition).where(PortfolioPosition.status == "closed")
    result = await db.execute(q)
    positions = list(result.scalars().all())
    metrics = compute_risk_metrics(positions)
    return RiskMetricsOut(
        sharpe_ratio=metrics.sharpe_ratio,
        sortino_ratio=metrics.sortino_ratio,
        max_drawdown_pct=metrics.max_drawdown_pct,
        profit_factor=metrics.profit_factor,
        avg_hold_hours=metrics.avg_hold_hours,
        total_closed=metrics.total_closed,
        wins=metrics.wins,
        losses=metrics.losses,
        win_rate=metrics.win_rate,
        breakdown_by_reason=metrics.breakdown_by_reason,
    )


@router.get("/equity-curve")
async def equity_curve(db: AsyncSession = Depends(get_db)):
    """Get equity curve computed from portfolio transactions."""
    from sqlalchemy import select
    from app.portfolio.models import PortfolioTransaction
    from app.portfolio.service import get_or_create_portfolio
    from app.portfolio.equity_curve import build_equity_curve, EquityCurveOut

    portfolio = await get_or_create_portfolio(db)
    q = (
        select(PortfolioTransaction)
        .where(PortfolioTransaction.portfolio_id == portfolio.id)
        .order_by(PortfolioTransaction.executed_at.asc())
    )
    result = await db.execute(q)
    rows = result.scalars().all()

    transactions = [
        {
            "tx_type": r.tx_type,
            "value_usd": float(r.value_usd),
            "executed_at": r.executed_at,
        }
        for r in rows
    ]

    points = build_equity_curve(transactions, float(portfolio.initial_capital))
    last = points[-1]
    max_dd = min(p.drawdown_pct for p in points)

    serialized = [
        {
            "timestamp": p.timestamp.isoformat(),
            "equity": p.equity,
            "cash": p.cash,
            "positions_value": p.positions_value,
            "drawdown_pct": p.drawdown_pct,
            "trade_number": p.trade_number,
        }
        for p in points
    ]

    return EquityCurveOut(
        points=serialized,
        total_points=len(serialized),
        current_equity=last.equity,
        max_drawdown_pct=round(max_dd, 6),
    )


@router.get("/journal/export/csv")
async def export_journal_csv(db: AsyncSession = Depends(get_db)):
    """Download closed trade history as CSV."""
    from fastapi.responses import Response
    from sqlalchemy import select
    from app.assets.models import Asset
    from app.portfolio.models import PortfolioPosition, PortfolioTransaction
    from app.portfolio.journal import format_journal_entry, format_journal
    from app.portfolio.export import format_journal_csv as _fmt_csv

    q = (
        select(PortfolioPosition, Asset.symbol)
        .join(Asset, PortfolioPosition.asset_id == Asset.id)
        .where(PortfolioPosition.status == "closed")
        .order_by(PortfolioPosition.closed_at.desc())
    )
    result = await db.execute(q)
    rows = result.all()

    positions = []
    for row in rows:
        pos = row.PortfolioPosition
        pos.symbol = row.symbol  # type: ignore[attr-defined]
        positions.append(pos)

    # Fetch transactions grouped by position_id
    position_ids = [pos.id for pos in positions]
    transactions_by_position: dict[str, list] = {str(pid): [] for pid in position_ids}
    if position_ids:
        tx_q = (
            select(PortfolioTransaction)
            .where(PortfolioTransaction.position_id.in_(position_ids))
            .order_by(PortfolioTransaction.executed_at.asc())
        )
        tx_result = await db.execute(tx_q)
        for tx in tx_result.scalars().all():
            key = str(tx.position_id)
            if key in transactions_by_position:
                transactions_by_position[key].append(tx)

    entries = format_journal(positions, transactions_by_position)
    csv_str = _fmt_csv(entries)

    return Response(
        content=csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="trade_journal.csv"'},
    )


@router.post("/positions/{position_id}/close")
async def close_position(position_id: UUID, db: AsyncSession = Depends(get_db)):
    """Manually close a demo position at current market price."""
    try:
        result = await manual_close_position(db, position_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

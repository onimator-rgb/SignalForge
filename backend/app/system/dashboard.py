"""Dashboard aggregate endpoint — single request for all dashboard widgets."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.models import AlertEvent
from app.anomalies.models import AnomalyEvent
from app.assets.models import Asset
from app.assets.service import get_latest_price
from app.portfolio.models import PortfolioPosition
from app.portfolio.service import get_or_create_portfolio
from app.recommendations.models import Recommendation
from app.watchlists.models import Watchlist, WatchlistAsset


async def get_dashboard_overview(db: AsyncSession) -> dict:
    """Aggregate data for the dashboard in a single call."""

    # ── Portfolio ─────────────────────────────────
    portfolio = await get_or_create_portfolio(db)
    pos_res = await db.execute(
        select(PortfolioPosition, Asset.symbol)
        .join(Asset, PortfolioPosition.asset_id == Asset.id)
        .where(PortfolioPosition.portfolio_id == portfolio.id, PortfolioPosition.status == "open")
    )
    positions = []
    positions_value = 0.0
    for row in pos_res.all():
        pos = row.PortfolioPosition
        price = await get_latest_price(db, pos.asset_id)
        cp = price.close if price else float(pos.entry_price)
        val = cp * float(pos.quantity)
        positions_value += val
        pnl = round((cp / float(pos.entry_price) - 1) * 100, 2) if float(pos.entry_price) > 0 else 0
        positions.append({"symbol": row.symbol, "pnl_pct": pnl, "asset_id": str(pos.asset_id)})

    cash = float(portfolio.current_cash)
    equity = round(cash + positions_value, 2)
    initial = float(portfolio.initial_capital)

    # ── Signals ───────────────────────────────────
    type_res = await db.execute(
        select(Recommendation.recommendation_type, func.count())
        .where(Recommendation.status == "active")
        .group_by(Recommendation.recommendation_type)
    )
    signal_counts = dict(type_res.all())

    top_res = await db.execute(
        select(Recommendation.id, Recommendation.asset_id, Recommendation.recommendation_type,
               Recommendation.score, Recommendation.confidence, Recommendation.risk_level,
               Asset.symbol, Asset.asset_class)
        .join(Asset, Recommendation.asset_id == Asset.id)
        .where(Recommendation.status == "active")
        .order_by(Recommendation.score.desc()).limit(5)
    )
    top_recs = [
        {"id": str(r.id), "asset_id": str(r.asset_id), "symbol": r.symbol,
         "asset_class": r.asset_class, "type": r.recommendation_type,
         "score": float(r.score), "confidence": r.confidence, "risk": r.risk_level}
        for r in top_res.all()
    ]

    # ── Alerts / Anomalies ────────────────────────
    unread = (await db.execute(select(func.count()).where(AlertEvent.is_read.is_(False)))).scalar_one()
    unresolved = (await db.execute(select(func.count()).where(AnomalyEvent.is_resolved.is_(False)))).scalar_one()

    crit_res = await db.execute(
        select(AnomalyEvent.anomaly_type, AnomalyEvent.severity, Asset.symbol)
        .join(Asset, AnomalyEvent.asset_id == Asset.id)
        .where(AnomalyEvent.is_resolved.is_(False), AnomalyEvent.severity.in_(["high", "critical"]))
        .order_by(AnomalyEvent.detected_at.desc()).limit(5)
    )
    critical = [{"symbol": r.symbol, "type": r.anomaly_type, "severity": r.severity} for r in crit_res.all()]

    # ── Watchlists ────────────────────────────────
    wl_res = await db.execute(
        select(Watchlist.id, Watchlist.name, func.count(WatchlistAsset.asset_id).label("cnt"))
        .outerjoin(WatchlistAsset, Watchlist.id == WatchlistAsset.watchlist_id)
        .group_by(Watchlist.id).order_by(Watchlist.created_at.desc()).limit(5)
    )
    watchlists = [{"id": str(r.id), "name": r.name, "asset_count": r.cnt} for r in wl_res.all()]

    return {
        "portfolio": {
            "equity": equity, "cash": cash,
            "total_return_pct": round((equity / initial - 1) * 100, 2) if initial > 0 else 0,
            "open_count": len(positions), "positions": positions,
        },
        "signals": {"counts": signal_counts, "top_recommendations": top_recs},
        "alerts": {"unread": unread, "unresolved_anomalies": unresolved, "critical": critical},
        "watchlists": watchlists,
    }

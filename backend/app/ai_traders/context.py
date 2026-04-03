"""Market context builder — assembles data for AI trader decisions.

Gathers indicators, anomalies, prices, portfolio state for a given asset
and packages it into a structured dict that gets serialized into the LLM prompt.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.market_data.models import PriceBar
from app.anomalies.models import AnomalyEvent
from app.recommendations.models import Recommendation
from app.portfolio.models import Portfolio, PortfolioPosition
from app.logging_config import get_logger
from app.news.aggregator import get_news_for_asset

log = get_logger(__name__)


async def build_asset_context(
    db: AsyncSession,
    asset_id: uuid.UUID,
    portfolio_id: uuid.UUID | None = None,
) -> dict:
    """Build comprehensive market context for a single asset."""
    now = datetime.now(timezone.utc)

    # Asset info
    asset = await db.get(Asset, asset_id)
    if not asset:
        return {"error": f"Asset {asset_id} not found"}

    ctx: dict = {
        "asset": {
            "id": str(asset_id),
            "symbol": asset.symbol,
            "name": asset.name,
            "asset_class": asset.asset_class,
        },
        "timestamp": now.isoformat(),
    }

    # Latest OHLCV bars (last 7 days, 1h interval)
    since = now - timedelta(days=7)
    bars_result = await db.execute(
        select(PriceBar)
        .where(
            PriceBar.asset_id == asset_id,
            PriceBar.interval == "1h",
            PriceBar.time >= since,
        )
        .order_by(PriceBar.time.desc())
        .limit(168)  # 7 days * 24h
    )
    bars = bars_result.scalars().all()

    if bars:
        latest = bars[0]
        ctx["price"] = {
            "current": float(latest.close),
            "open_24h": float(bars[min(23, len(bars) - 1)].open) if len(bars) > 1 else float(latest.open),
            "high_24h": max(float(b.high) for b in bars[:24]),
            "low_24h": min(float(b.low) for b in bars[:24]),
            "volume_24h": sum(float(b.volume) for b in bars[:24]),
        }
        if len(bars) > 1 and float(bars[min(23, len(bars) - 1)].open) > 0:
            open_24h = float(bars[min(23, len(bars) - 1)].open)
            ctx["price"]["change_24h_pct"] = round(
                (float(latest.close) - open_24h) / open_24h * 100, 2
            )
        # Price history for trend analysis (daily closes, last 7 days)
        daily_closes = []
        for i in range(0, min(len(bars), 168), 24):
            daily_closes.append(round(float(bars[i].close), 2))
        ctx["price"]["daily_closes_7d"] = daily_closes
    else:
        ctx["price"] = {"current": None, "note": "No recent price data"}

    # Indicators (from latest recommendation if available)
    rec_result = await db.execute(
        select(Recommendation)
        .where(Recommendation.asset_id == asset_id)
        .order_by(Recommendation.generated_at.desc())
        .limit(1)
    )
    rec = rec_result.scalar_one_or_none()

    if rec:
        breakdown = rec.signal_breakdown or {}
        ctx["indicators"] = {
            "composite_score": float(rec.score) if rec.score else None,
            "recommendation_type": rec.recommendation_type,
            "confidence": rec.confidence,
            "risk_level": rec.risk_level,
            "signal_breakdown": breakdown,
        }
    else:
        ctx["indicators"] = {"note": "No recent recommendation data"}

    # Active anomalies (last 48h)
    anom_since = now - timedelta(hours=48)
    anom_result = await db.execute(
        select(AnomalyEvent)
        .where(
            AnomalyEvent.asset_id == asset_id,
            AnomalyEvent.detected_at >= anom_since,
        )
        .order_by(AnomalyEvent.detected_at.desc())
        .limit(10)
    )
    anomalies = anom_result.scalars().all()
    ctx["anomalies"] = [
        {
            "type": a.anomaly_type,
            "severity": a.severity,
            "score": float(a.score),
            "detected_at": a.detected_at.isoformat(),
        }
        for a in anomalies
    ]

    # Recent verified news
    try:
        news = await get_news_for_asset(db, asset.symbol, hours=24, limit=5)
        if news:
            ctx["news"] = news
    except Exception:
        pass  # News is non-critical — don't break trading on news fetch failure

    # Portfolio state for this trader
    if portfolio_id:
        pos_result = await db.execute(
            select(PortfolioPosition).where(
                PortfolioPosition.portfolio_id == portfolio_id,
                PortfolioPosition.asset_id == asset_id,
                PortfolioPosition.status == "open",
            )
        )
        open_pos = pos_result.scalar_one_or_none()
        if open_pos:
            ctx["existing_position"] = {
                "entry_price": float(open_pos.entry_price),
                "quantity": float(open_pos.quantity),
                "entry_value_usd": float(open_pos.entry_value_usd),
                "opened_at": open_pos.opened_at.isoformat(),
                "stop_loss": float(open_pos.stop_loss_price) if open_pos.stop_loss_price else None,
                "take_profit": float(open_pos.take_profit_price) if open_pos.take_profit_price else None,
            }
            if ctx["price"].get("current"):
                unrealized_pct = (ctx["price"]["current"] - float(open_pos.entry_price)) / float(open_pos.entry_price) * 100
                ctx["existing_position"]["unrealized_pnl_pct"] = round(unrealized_pct, 2)

        # Portfolio cash
        port_result = await db.execute(
            select(Portfolio).where(Portfolio.id == portfolio_id)
        )
        portfolio = port_result.scalar_one_or_none()
        if portfolio:
            ctx["portfolio"] = {
                "cash_available": float(portfolio.current_cash),
                "initial_capital": float(portfolio.initial_capital),
            }
            # Count open positions
            count_result = await db.execute(
                select(func.count()).where(
                    PortfolioPosition.portfolio_id == portfolio_id,
                    PortfolioPosition.status == "open",
                )
            )
            ctx["portfolio"]["open_positions_count"] = count_result.scalar_one()

    return ctx


async def build_multi_asset_context(
    db: AsyncSession,
    asset_ids: list[uuid.UUID],
    portfolio_id: uuid.UUID | None = None,
) -> list[dict]:
    """Build context for multiple assets (for batch evaluation)."""
    contexts = []
    for aid in asset_ids:
        ctx = await build_asset_context(db, aid, portfolio_id)
        contexts.append(ctx)
    return contexts

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
from .models import AITrader, AITraderDecision, AITraderSnapshot

log = get_logger(__name__)


async def build_asset_context(
    db: AsyncSession,
    asset_id: uuid.UUID,
    portfolio_id: uuid.UUID | None = None,
    trader_id: uuid.UUID | None = None,
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

    # Multi-timeframe: 4h bars for medium-term trend
    bars_4h_result = await db.execute(
        select(PriceBar)
        .where(
            PriceBar.asset_id == asset_id,
            PriceBar.interval == "4h",
            PriceBar.time >= since,
        )
        .order_by(PriceBar.time.desc())
        .limit(42)  # 7 days * 6 bars/day
    )
    bars_4h = bars_4h_result.scalars().all()
    if bars_4h:
        closes_4h = [round(float(b.close), 2) for b in bars_4h[:12]]  # last 2 days
        ctx["price"]["closes_4h"] = closes_4h
        if len(bars_4h) >= 6:
            ctx["price"]["change_4h_pct"] = round(
                (float(bars_4h[0].close) - float(bars_4h[5].close)) / float(bars_4h[5].close) * 100, 2
            )

    # Multi-timeframe: 1d bars for long-term trend
    bars_1d_result = await db.execute(
        select(PriceBar)
        .where(
            PriceBar.asset_id == asset_id,
            PriceBar.interval == "1d",
            PriceBar.time >= now - timedelta(days=30),
        )
        .order_by(PriceBar.time.desc())
        .limit(30)
    )
    bars_1d = bars_1d_result.scalars().all()
    if bars_1d:
        closes_1d = [round(float(b.close), 2) for b in bars_1d[:14]]  # last 2 weeks
        ctx["price"]["closes_1d"] = closes_1d
        if len(bars_1d) >= 7:
            ctx["price"]["change_7d_pct"] = round(
                (float(bars_1d[0].close) - float(bars_1d[6].close)) / float(bars_1d[6].close) * 100, 2
            )
        if len(bars_1d) >= 30:
            ctx["price"]["change_30d_pct"] = round(
                (float(bars_1d[0].close) - float(bars_1d[29].close)) / float(bars_1d[29].close) * 100, 2
            )

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

    # Trader memory — recent performance on this asset
    if trader_id:
        try:
            # Recent decisions on this asset
            decisions_result = await db.execute(
                select(AITraderDecision)
                .where(
                    AITraderDecision.trader_id == trader_id,
                    AITraderDecision.asset_id == asset_id,
                )
                .order_by(AITraderDecision.created_at.desc())
                .limit(10)
            )
            recent_decisions = [
                {
                    "action": d.action,
                    "confidence": float(d.confidence) if d.confidence else 0,
                    "executed": d.executed,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                }
                for d in decisions_result.scalars().all()
            ]

            # Recent closed trades
            recent_trades = []
            if portfolio_id:
                trades_result = await db.execute(
                    select(PortfolioPosition)
                    .where(
                        PortfolioPosition.portfolio_id == portfolio_id,
                        PortfolioPosition.status == "closed",
                    )
                    .order_by(PortfolioPosition.closed_at.desc())
                    .limit(10)
                )
                recent_trades = [
                    {
                        "realized_pnl_pct": round(float(p.realized_pnl_pct), 2) if p.realized_pnl_pct else 0,
                        "close_reason": p.close_reason or "unknown",
                    }
                    for p in trades_result.scalars().all()
                ]

            # Overall stats
            trader_obj = await db.get(AITrader, trader_id)
            total_trades = (trader_obj.win_count + trader_obj.loss_count) if trader_obj else 0
            win_rate = round(trader_obj.win_count / total_trades * 100, 1) if total_trades > 0 else 0

            ctx["trader_memory"] = {
                "recent_decisions": recent_decisions,
                "recent_trades": recent_trades,
                "overall_stats": {
                    "win_rate": win_rate,
                    "total_trades": total_trades,
                    "wins": trader_obj.win_count if trader_obj else 0,
                    "losses": trader_obj.loss_count if trader_obj else 0,
                },
            }
        except Exception:
            pass  # Non-critical — proceed without memory

    return ctx


async def calc_market_regime(db: AsyncSession) -> dict:
    """Determine current market regime from BTC price action and overall scores."""
    import statistics

    regime = {"regime": "unknown", "btc_7d_change_pct": 0, "avg_composite_score": 50, "volatility_index": 0}

    try:
        # Find BTC asset
        btc_result = await db.execute(
            select(Asset).where(Asset.symbol.in_(["BTC", "BTCUSDT"]))
        )
        btc = btc_result.scalar_one_or_none()

        if btc:
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            bars_result = await db.execute(
                select(PriceBar)
                .where(
                    PriceBar.asset_id == btc.id,
                    PriceBar.interval == "1h",
                    PriceBar.time >= cutoff,
                )
                .order_by(PriceBar.time.asc())
            )
            bars = bars_result.scalars().all()

            if len(bars) >= 24:
                closes = [float(b.close) for b in bars]
                oldest = closes[0]
                newest = closes[-1]
                regime["btc_7d_change_pct"] = round((newest - oldest) / oldest * 100, 2)

                # Volatility: stddev of hourly returns
                returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]
                regime["volatility_index"] = round(statistics.stdev(returns) * 100, 4) if len(returns) > 1 else 0

        # Average composite score across all recent recommendations
        from app.recommendations.models import Recommendation
        score_result = await db.execute(
            select(func.avg(Recommendation.score))
            .where(Recommendation.generated_at >= datetime.now(timezone.utc) - timedelta(hours=24))
        )
        avg_score = score_result.scalar_one_or_none()
        if avg_score:
            regime["avg_composite_score"] = round(float(avg_score), 1)

        # Classify regime
        btc_change = regime["btc_7d_change_pct"]
        vol = regime["volatility_index"]
        avg_sc = regime["avg_composite_score"]

        if vol > 1.5:
            regime["regime"] = "volatile"
        elif btc_change > 5 and avg_sc > 55:
            regime["regime"] = "trending_up"
        elif btc_change < -5 and avg_sc < 45:
            regime["regime"] = "trending_down"
        else:
            regime["regime"] = "ranging"

    except Exception:
        pass  # Non-critical

    return regime


async def calc_consensus(db: AsyncSession, asset_id: uuid.UUID) -> dict:
    """Calculate trader consensus for an asset based on most recent decisions."""
    result = await db.execute(
        select(AITrader).where(AITrader.is_active.is_(True))
    )
    traders = result.scalars().all()

    counts = {"buy": 0, "sell": 0, "hold": 0, "skip": 0}
    total = 0

    for trader in traders:
        dec_result = await db.execute(
            select(AITraderDecision)
            .where(
                AITraderDecision.trader_id == trader.id,
                AITraderDecision.asset_id == asset_id,
            )
            .order_by(AITraderDecision.created_at.desc())
            .limit(1)
        )
        dec = dec_result.scalar_one_or_none()
        if dec and dec.action in counts:
            counts[dec.action] += 1
            total += 1

    bullish_pct = counts["buy"] / total if total > 0 else 0

    return {
        "total_traders": total,
        "buy": counts["buy"],
        "sell": counts["sell"],
        "hold": counts["hold"],
        "skip": counts["skip"],
        "bullish_pct": round(bullish_pct, 2),
    }


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

"""Report generation service — builds context, calls LLM, persists result."""

import time as _time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.anomalies.models import AnomalyEvent
from app.assets.models import Asset
from app.assets.service import get_latest_price
from app.indicators.service import get_indicators
from app.llm.client import llm_complete
from app.llm.prompts import anomaly_explanation, asset_brief, market_summary
from app.logging_config import get_logger
from app.market_data.models import PriceBar
from app.reports.models import AnalysisReport

log = get_logger(__name__)

VALID_REPORT_TYPES = {"asset_brief", "anomaly_explanation", "market_summary", "watchlist_summary"}
MAX_REPORTS_PER_HOUR = 20


async def check_rate_limit(db: AsyncSession) -> None:
    """Raise ValueError if report rate limit is exceeded."""
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    result = await db.execute(
        select(func.count(AnalysisReport.id)).where(
            AnalysisReport.created_at >= one_hour_ago,
        )
    )
    count = result.scalar_one()
    if count >= MAX_REPORTS_PER_HOUR:
        raise ValueError(
            f"Rate limit: {count}/{MAX_REPORTS_PER_HOUR} reports in the last hour. Please wait."
        )


async def generate_report(
    db: AsyncSession,
    report_type: str,
    asset_id: uuid.UUID | None = None,
    anomaly_event_id: uuid.UUID | None = None,
    alert_event_id: uuid.UUID | None = None,
    watchlist_id: uuid.UUID | None = None,
) -> AnalysisReport:
    if report_type not in VALID_REPORT_TYPES:
        raise ValueError(f"Invalid report_type: {report_type}")

    await check_rate_limit(db)

    report = AnalysisReport(
        report_type=report_type,
        status="pending",
        asset_id=asset_id,
        anomaly_event_id=anomaly_event_id,
        alert_event_id=alert_event_id,
    )
    db.add(report)
    await db.flush()

    log.info(
        "report.generate_start",
        report_id=str(report.id),
        report_type=report_type,
        asset_id=str(asset_id) if asset_id else None,
        anomaly_event_id=str(anomaly_event_id) if anomaly_event_id else None,
        alert_event_id=str(alert_event_id) if alert_event_id else None,
    )

    t_start = _time.monotonic()
    try:
        report.status = "generating"
        await db.flush()

        context = await _build_context(db, report_type, asset_id, anomaly_event_id, watchlist_id)
        system_prompt, user_prompt, prompt_version = _get_prompts(report_type, context)
        report.context_data = context
        report.prompt_version = prompt_version

        llm_response = await llm_complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,
            max_tokens=2000,
        )

        duration_ms = int((_time.monotonic() - t_start) * 1000)
        report.content_md = llm_response.content
        report.title = _generate_title(report_type, context)
        report.llm_provider = llm_response.provider
        report.llm_model = llm_response.model
        report.token_usage = {
            "input_tokens": llm_response.input_tokens,
            "output_tokens": llm_response.output_tokens,
            "duration_ms": duration_ms,
        }
        report.status = "completed"
        report.completed_at = datetime.now(timezone.utc)

        log.info(
            "report.generate_done",
            report_id=str(report.id),
            report_type=report_type,
            provider=llm_response.provider,
            model=llm_response.model,
            input_tokens=llm_response.input_tokens,
            output_tokens=llm_response.output_tokens,
            duration_ms=duration_ms,
        )
    except Exception as e:
        duration_ms = int((_time.monotonic() - t_start) * 1000)
        report.status = "failed"
        report.error_message = str(e)[:1000]
        report.token_usage = {"duration_ms": duration_ms}
        log.error(
            "report.generate_error",
            report_id=str(report.id),
            report_type=report_type,
            error=str(e),
            duration_ms=duration_ms,
        )

    await db.commit()
    return report


async def retry_report(db: AsyncSession, report_id: uuid.UUID) -> AnalysisReport:
    """Retry a failed report by creating a new one with the same parameters."""
    result = await db.execute(
        select(AnalysisReport).where(AnalysisReport.id == report_id)
    )
    original = result.scalar_one_or_none()
    if not original:
        raise ValueError(f"Report {report_id} not found")
    if original.status != "failed":
        raise ValueError(f"Only failed reports can be retried (current: {original.status})")

    log.info("report.retry_start", original_id=str(report_id), report_type=original.report_type)

    return await generate_report(
        db=db,
        report_type=original.report_type,
        asset_id=original.asset_id,
        anomaly_event_id=original.anomaly_event_id,
        alert_event_id=original.alert_event_id,
    )


async def _build_context(db, report_type, asset_id, anomaly_event_id, watchlist_id=None):
    if report_type == "asset_brief":
        if not asset_id:
            raise ValueError("asset_id required for asset_brief")
        return await _build_asset_context(db, asset_id)
    elif report_type == "anomaly_explanation":
        if not anomaly_event_id:
            raise ValueError("anomaly_event_id required for anomaly_explanation")
        return await _build_anomaly_context(db, anomaly_event_id)
    elif report_type == "market_summary":
        return await _build_market_context(db)
    elif report_type == "watchlist_summary":
        if not watchlist_id:
            raise ValueError("watchlist_id required for watchlist_summary")
        return await _build_watchlist_context(db, watchlist_id)
    raise ValueError(f"Unknown report_type: {report_type}")


async def _build_asset_context(db: AsyncSession, asset_id: uuid.UUID) -> dict:
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise ValueError(f"Asset {asset_id} not found")

    price_data = await get_latest_price(db, asset_id)
    ind = await get_indicators(db, asset_id, asset.symbol, interval="1h")

    anom_result = await db.execute(
        select(AnomalyEvent).where(AnomalyEvent.asset_id == asset_id)
        .order_by(AnomalyEvent.detected_at.desc()).limit(5)
    )
    anomalies = anom_result.scalars().all()

    ohlcv_result = await db.execute(
        sql_text("""
            SELECT max(high) as high, min(low) as low, avg(volume) as avg_vol
            FROM (SELECT high, low, volume FROM price_bars
                  WHERE asset_id = :aid AND interval = '1h'
                  ORDER BY time DESC LIMIT 48) sub
        """), {"aid": asset_id},
    )
    ohlcv_row = ohlcv_result.fetchone()

    return {
        "asset": {
            "symbol": asset.symbol, "name": asset.name,
            "market_cap_rank": asset.market_cap_rank,
            "asset_class": asset.asset_class,
            "exchange": asset.exchange, "currency": asset.currency,
        },
        "latest_price": {
            "close": price_data.close if price_data else None,
            "change_24h_pct": price_data.change_24h_pct if price_data else None,
            "bar_time": str(price_data.bar_time) if price_data else None,
        },
        "indicators": {
            "rsi_14": ind.rsi_14 if ind else None,
            "macd": f"macd={ind.macd.macd}, signal={ind.macd.signal}, hist={ind.macd.histogram}" if ind and ind.macd else None,
            "bb_upper": ind.bollinger.upper if ind and ind.bollinger else None,
            "bb_middle": ind.bollinger.middle if ind and ind.bollinger else None,
            "bb_lower": ind.bollinger.lower if ind and ind.bollinger else None,
        },
        "recent_anomalies": [
            {"anomaly_type": a.anomaly_type, "severity": a.severity, "score": float(a.score), "detected_at": str(a.detected_at)}
            for a in anomalies
        ],
        "ohlcv_summary": {
            "high": round(float(ohlcv_row[0]), 2) if ohlcv_row and ohlcv_row[0] else None,
            "low": round(float(ohlcv_row[1]), 2) if ohlcv_row and ohlcv_row[1] else None,
            "avg_volume": round(float(ohlcv_row[2]), 2) if ohlcv_row and ohlcv_row[2] else None,
        },
    }


async def _build_anomaly_context(db: AsyncSession, anomaly_event_id: uuid.UUID) -> dict:
    result = await db.execute(select(AnomalyEvent).where(AnomalyEvent.id == anomaly_event_id))
    anomaly = result.scalar_one_or_none()
    if not anomaly:
        raise ValueError(f"AnomalyEvent {anomaly_event_id} not found")

    asset_result = await db.execute(select(Asset).where(Asset.id == anomaly.asset_id))
    asset = asset_result.scalar_one_or_none()
    if not asset:
        raise ValueError("Asset for anomaly not found")

    price_data = await get_latest_price(db, anomaly.asset_id)
    ind = await get_indicators(db, anomaly.asset_id, asset.symbol, interval="1h")

    return {
        "anomaly": {
            "anomaly_type": anomaly.anomaly_type, "severity": anomaly.severity,
            "score": float(anomaly.score), "detected_at": str(anomaly.detected_at),
            "timeframe": anomaly.timeframe, "details": anomaly.details or {},
        },
        "asset": {"symbol": asset.symbol, "name": asset.name, "asset_class": asset.asset_class},
        "latest_price": {
            "close": price_data.close if price_data else None,
            "change_24h_pct": price_data.change_24h_pct if price_data else None,
        },
        "indicators": {
            "rsi_14": ind.rsi_14 if ind else None,
            "macd_histogram": ind.macd.histogram if ind and ind.macd else None,
        },
    }


async def _build_market_context(db: AsyncSession) -> dict:
    from app.assets.service import get_asset_list

    items, total = await get_asset_list(db, sort_by="change_24h", sort_dir="desc", limit=10)

    total_res = await db.execute(select(func.count(AnomalyEvent.id)))
    unresolved_res = await db.execute(
        select(func.count(AnomalyEvent.id)).where(AnomalyEvent.is_resolved.is_(False))
    )
    active_result = await db.execute(
        select(AnomalyEvent, Asset.symbol, Asset.asset_class)
        .join(Asset, AnomalyEvent.asset_id == Asset.id)
        .where(AnomalyEvent.is_resolved.is_(False))
        .order_by(AnomalyEvent.detected_at.desc()).limit(10)
    )

    return {
        "asset_count": total,
        "top_movers": [
            {"symbol": a.symbol, "asset_class": a.asset_class,
             "close": a.latest_price.close if a.latest_price else None,
             "change_24h_pct": a.latest_price.change_24h_pct if a.latest_price else None}
            for a in items
        ],
        "anomaly_stats": {"total": total_res.scalar_one(), "unresolved": unresolved_res.scalar_one()},
        "active_anomalies": [
            {"asset_symbol": symbol, "asset_class": ac, "anomaly_type": a.anomaly_type, "severity": a.severity}
            for a, symbol, ac in active_result.all()
        ],
    }


async def _build_watchlist_context(db: AsyncSession, watchlist_id: uuid.UUID) -> dict:
    """Build context for watchlist_summary report."""
    from app.watchlists.models import Watchlist, WatchlistAsset
    from app.recommendations.models import Recommendation
    from app.portfolio.models import PortfolioPosition

    wl_res = await db.execute(select(Watchlist).where(Watchlist.id == watchlist_id))
    wl = wl_res.scalar_one_or_none()
    if not wl:
        raise ValueError(f"Watchlist {watchlist_id} not found")

    wa_res = await db.execute(
        select(WatchlistAsset.asset_id).where(WatchlistAsset.watchlist_id == watchlist_id)
    )
    asset_ids = [r[0] for r in wa_res.all()]
    if not asset_ids:
        return {"watchlist": {"name": wl.name, "total": 0}, "assets": [], "recommendations": [], "portfolio_overlap": [], "anomalies": []}

    # Assets with prices
    from sqlalchemy import func as sqlfunc
    assets_res = await db.execute(
        select(Asset).where(Asset.id.in_(asset_ids)).order_by(Asset.symbol)
    )
    assets_list = []
    class_counts = {"crypto": 0, "stock": 0}
    for asset in assets_res.scalars().all():
        price_data = await get_latest_price(db, asset.id)
        class_counts[asset.asset_class] = class_counts.get(asset.asset_class, 0) + 1
        assets_list.append({
            "symbol": asset.symbol, "asset_class": asset.asset_class,
            "price": price_data.close if price_data else None,
            "change_24h_pct": price_data.change_24h_pct if price_data else None,
        })

    # Recommendations
    rec_res = await db.execute(
        select(Recommendation.asset_id, Recommendation.recommendation_type,
               Recommendation.score, Recommendation.confidence, Recommendation.risk_level,
               Asset.symbol)
        .join(Asset, Recommendation.asset_id == Asset.id)
        .where(Recommendation.asset_id.in_(asset_ids), Recommendation.status == "active")
        .order_by(Recommendation.score.desc())
    )
    recs_list = [
        {"symbol": r.symbol, "type": r.recommendation_type, "score": float(r.score),
         "confidence": r.confidence, "risk": r.risk_level}
        for r in rec_res.all()
    ]

    # Portfolio overlap
    pos_res = await db.execute(
        select(PortfolioPosition.asset_id, PortfolioPosition.entry_price,
               Asset.symbol)
        .join(Asset, PortfolioPosition.asset_id == Asset.id)
        .where(PortfolioPosition.asset_id.in_(asset_ids), PortfolioPosition.status == "open")
    )
    overlap = []
    for r in pos_res.all():
        price_data = await get_latest_price(db, r.asset_id)
        pnl_pct = round((price_data.close / float(r.entry_price) - 1) * 100, 2) if price_data and float(r.entry_price) > 0 else 0
        overlap.append({"symbol": r.symbol, "pnl_pct": pnl_pct})

    # Anomalies
    anom_res = await db.execute(
        select(AnomalyEvent.anomaly_type, AnomalyEvent.severity, Asset.symbol)
        .join(Asset, AnomalyEvent.asset_id == Asset.id)
        .where(AnomalyEvent.asset_id.in_(asset_ids), AnomalyEvent.is_resolved.is_(False))
        .order_by(AnomalyEvent.detected_at.desc()).limit(10)
    )
    anomalies_list = [
        {"symbol": r.symbol, "type": r.anomaly_type, "severity": r.severity}
        for r in anom_res.all()
    ]

    return {
        "watchlist": {"name": wl.name, "total": len(asset_ids), "crypto": class_counts.get("crypto", 0), "stock": class_counts.get("stock", 0)},
        "assets": assets_list,
        "recommendations": recs_list,
        "portfolio_overlap": overlap,
        "anomalies": anomalies_list,
    }


def _get_prompts(report_type, context):
    if report_type == "asset_brief":
        return asset_brief.SYSTEM, asset_brief.build_user_prompt(context), asset_brief.VERSION
    elif report_type == "anomaly_explanation":
        return anomaly_explanation.SYSTEM, anomaly_explanation.build_user_prompt(context), anomaly_explanation.VERSION
    elif report_type == "market_summary":
        return market_summary.SYSTEM, market_summary.build_user_prompt(context), market_summary.VERSION
    elif report_type == "watchlist_summary":
        from app.llm.prompts import watchlist_summary
        return watchlist_summary.SYSTEM, watchlist_summary.build_user_prompt(context), watchlist_summary.VERSION
    raise ValueError(f"No prompts for: {report_type}")


def _generate_title(report_type, context):
    if report_type == "asset_brief":
        return f"Asset Brief: {context.get('asset', {}).get('symbol', '?')}"
    elif report_type == "anomaly_explanation":
        sym = context.get("asset", {}).get("symbol", "?")
        atype = context.get("anomaly", {}).get("anomaly_type", "?").replace("_", " ")
        return f"Anomaly: {sym} — {atype}"
    elif report_type == "market_summary":
        return "Market Summary"
    elif report_type == "watchlist_summary":
        name = context.get("watchlist", {}).get("name", "Watchlist")
        return f"Watchlist Summary: {name}"
    return "Report"

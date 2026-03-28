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

VALID_REPORT_TYPES = {"asset_brief", "anomaly_explanation", "market_summary"}
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
) -> AnalysisReport:
    if report_type not in VALID_REPORT_TYPES:
        raise ValueError(f"Invalid report_type: {report_type}")

    await check_rate_limit(db)

    report = AnalysisReport(
        report_type=report_type,
        status="pending",
        asset_id=asset_id,
        anomaly_event_id=anomaly_event_id,
    )
    db.add(report)
    await db.flush()

    log.info(
        "report.generate_start",
        report_id=str(report.id),
        report_type=report_type,
        asset_id=str(asset_id) if asset_id else None,
        anomaly_event_id=str(anomaly_event_id) if anomaly_event_id else None,
    )

    t_start = _time.monotonic()
    try:
        report.status = "generating"
        await db.flush()

        context = await _build_context(db, report_type, asset_id, anomaly_event_id)
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
    )


async def _build_context(db, report_type, asset_id, anomaly_event_id):
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
        "asset": {"symbol": asset.symbol, "name": asset.name, "market_cap_rank": asset.market_cap_rank},
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
        "asset": {"symbol": asset.symbol, "name": asset.name},
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
        select(AnomalyEvent, Asset.symbol)
        .join(Asset, AnomalyEvent.asset_id == Asset.id)
        .where(AnomalyEvent.is_resolved.is_(False))
        .order_by(AnomalyEvent.detected_at.desc()).limit(10)
    )

    return {
        "asset_count": total,
        "top_movers": [
            {"symbol": a.symbol, "close": a.latest_price.close if a.latest_price else None,
             "change_24h_pct": a.latest_price.change_24h_pct if a.latest_price else None}
            for a in items
        ],
        "anomaly_stats": {"total": total_res.scalar_one(), "unresolved": unresolved_res.scalar_one()},
        "active_anomalies": [
            {"asset_symbol": symbol, "anomaly_type": a.anomaly_type, "severity": a.severity}
            for a, symbol in active_result.all()
        ],
    }


def _get_prompts(report_type, context):
    if report_type == "asset_brief":
        return asset_brief.SYSTEM, asset_brief.build_user_prompt(context), asset_brief.VERSION
    elif report_type == "anomaly_explanation":
        return anomaly_explanation.SYSTEM, anomaly_explanation.build_user_prompt(context), anomaly_explanation.VERSION
    elif report_type == "market_summary":
        return market_summary.SYSTEM, market_summary.build_user_prompt(context), market_summary.VERSION
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
    return "Report"

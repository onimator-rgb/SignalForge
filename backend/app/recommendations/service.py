"""Recommendation service — generates, supersedes, and expires recommendations."""

import time as _time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, select, text as sql_text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.anomalies.models import AnomalyEvent
from app.assets.models import Asset
from app.assets.service import get_latest_price
from app.indicators.service import get_indicators
from app.logging_config import get_logger
from app.market_data.models import PriceBar
from app.recommendations.models import Recommendation
from app.recommendations.scoring import compute_recommendation

log = get_logger(__name__)

RECOMMENDATION_VALIDITY_HOURS = 48


async def generate_recommendations_batch(
    db: AsyncSession,
    asset_ids_symbols: list[tuple[uuid.UUID, str]],
    interval: str = "1h",
) -> int:
    """Generate recommendations for a batch of assets. Returns count generated."""
    t_start = _time.monotonic()
    generated = 0

    for asset_id, symbol in asset_ids_symbols:
        try:
            rec = await _generate_for_asset(db, asset_id, symbol, interval)
            if rec:
                generated += 1
        except Exception as e:
            log.error("recommendation.generate_error", asset=symbol, error=str(e))

    duration_ms = int((_time.monotonic() - t_start) * 1000)
    log.info(
        "recommendation.batch_done",
        assets=len(asset_ids_symbols),
        generated=generated,
        duration_ms=duration_ms,
    )
    return generated


async def _generate_for_asset(
    db: AsyncSession,
    asset_id: uuid.UUID,
    symbol: str,
    interval: str,
) -> Recommendation | None:
    """Generate a single recommendation for an asset."""
    # Load asset for asset_class
    asset_res = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = asset_res.scalar_one_or_none()
    if not asset:
        return None

    # Get indicators
    indicators = await get_indicators(db, asset_id, symbol, interval)
    if indicators is None or indicators.bars_available < 20:
        return None  # Not enough data

    # Get latest price + 24h change
    price = await get_latest_price(db, asset_id)
    change_24h = price.change_24h_pct if price else None

    # Volume context: latest bar vs avg of last 20 bars
    avg_vol, latest_vol = await _get_volume_context(db, asset_id, interval)

    # Anomaly context
    anomaly_count = await _count_unresolved_anomalies(db, asset_id)
    has_rsi_oversold = await _has_rsi_extreme_oversold(db, asset_id)

    # Score
    result = compute_recommendation(
        indicators=indicators,
        change_24h_pct=change_24h,
        avg_volume=avg_vol,
        latest_volume=latest_vol,
        unresolved_anomalies=anomaly_count,
        has_rsi_extreme_oversold=has_rsi_oversold,
        asset_class=asset.asset_class,
        asset_symbol=symbol,
    )

    now = datetime.now(timezone.utc)

    # Supersede previous active recommendation for this asset
    await db.execute(
        update(Recommendation)
        .where(
            Recommendation.asset_id == asset_id,
            Recommendation.status == "active",
        )
        .values(status="superseded", updated_at=now)
    )

    # Create new recommendation
    rec = Recommendation(
        asset_id=asset_id,
        generated_at=now,
        recommendation_type=result.recommendation_type,
        score=result.composite_score,
        confidence=result.confidence,
        risk_level=result.risk_level,
        rationale_summary=result.rationale_summary,
        signal_breakdown=result.signal_breakdown,
        entry_price_snapshot=price.close if price else None,
        time_horizon="24h-72h",
        valid_until=now + timedelta(hours=RECOMMENDATION_VALIDITY_HOURS),
        status="active",
    )
    db.add(rec)
    await db.flush()

    log.info(
        "recommendation.generate_done",
        asset=symbol,
        asset_class=asset.asset_class,
        recommendation_type=result.recommendation_type,
        score=result.composite_score,
        confidence=result.confidence,
        risk_level=result.risk_level,
    )

    return rec


async def expire_stale_recommendations(db: AsyncSession) -> int:
    """Mark expired recommendations. Returns count expired."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        update(Recommendation)
        .where(
            Recommendation.status == "active",
            Recommendation.valid_until < now,
        )
        .values(status="expired", updated_at=now)
    )
    count = result.rowcount
    if count:
        log.info("recommendation.expired", count=count)
    return count


async def _get_volume_context(
    db: AsyncSession, asset_id: uuid.UUID, interval: str
) -> tuple[float | None, float | None]:
    """Get average volume (last 20 bars) and latest volume."""
    result = await db.execute(
        sql_text("""
            SELECT volume, row_number() OVER (ORDER BY time DESC) as rn
            FROM price_bars
            WHERE asset_id = :aid AND interval = :interval
            ORDER BY time DESC
            LIMIT 21
        """),
        {"aid": asset_id, "interval": interval},
    )
    rows = result.fetchall()
    if len(rows) < 2:
        return None, None

    latest_vol = float(rows[0].volume)
    avg_vol = sum(float(r.volume) for r in rows[1:]) / len(rows[1:])
    return avg_vol, latest_vol


async def _count_unresolved_anomalies(db: AsyncSession, asset_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count(AnomalyEvent.id)).where(
            and_(AnomalyEvent.asset_id == asset_id, AnomalyEvent.is_resolved.is_(False))
        )
    )
    return result.scalar_one()


async def _has_rsi_extreme_oversold(db: AsyncSession, asset_id: uuid.UUID) -> bool:
    """Check if there's an active RSI extreme anomaly of oversold type."""
    result = await db.execute(
        select(func.count(AnomalyEvent.id)).where(
            and_(
                AnomalyEvent.asset_id == asset_id,
                AnomalyEvent.is_resolved.is_(False),
                AnomalyEvent.anomaly_type == "rsi_extreme",
            )
        )
    )
    return result.scalar_one() > 0

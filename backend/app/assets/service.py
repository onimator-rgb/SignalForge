"""Asset service — queries for latest price, 24h change, anomaly counts."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import Row, and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.anomalies.models import AnomalyEvent
from app.assets.models import Asset
from app.assets.schemas import AssetIndicatorsSummary, AssetListItem, LatestPrice
from app.indicators.service import get_indicators
from app.logging_config import get_logger
from app.market_data.models import PriceBar

log = get_logger(__name__)

# Default interval for latest-price / 24h-change calculations
PRICE_INTERVAL = "1h"


async def get_asset_list(
    db: AsyncSession,
    active_only: bool = True,
    asset_class: str | None = None,
    sort_by: str = "market_cap_rank",
    sort_dir: str = "asc",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AssetListItem], int]:
    """Load paginated asset list with latest price and anomaly count.

    Uses a single SQL query to fetch latest close + 24h-ago close for each asset,
    plus unresolved anomaly counts.

    Returns (items, total_count).
    """
    # Count total
    count_q = select(func.count(Asset.id))
    if active_only:
        count_q = count_q.where(Asset.is_active.is_(True))
    if asset_class:
        count_q = count_q.where(Asset.asset_class == asset_class)
    total_res = await db.execute(count_q)
    total = total_res.scalar_one()

    # Main query: assets + latest price data + anomaly counts via SQL
    # This avoids N+1: one query instead of per-asset calls.
    result = await db.execute(
        text("""
            WITH latest_bars AS (
                SELECT DISTINCT ON (asset_id)
                    asset_id,
                    "close" AS latest_close,
                    "time" AS bar_time
                FROM price_bars
                WHERE interval = :interval
                ORDER BY asset_id, "time" DESC
            ),
            bars_24h_ago AS (
                SELECT DISTINCT ON (asset_id)
                    asset_id,
                    "close" AS close_24h
                FROM price_bars
                WHERE interval = :interval
                  AND "time" <= (now() AT TIME ZONE 'UTC' - INTERVAL '24 hours')
                ORDER BY asset_id, "time" DESC
            ),
            anomaly_counts AS (
                SELECT asset_id, count(*) AS cnt
                FROM anomaly_events
                WHERE is_resolved = false
                GROUP BY asset_id
            )
            SELECT
                a.id, a.symbol, a.name, a.asset_class, a.market_cap_rank, a.is_active,
                a.metadata->>'image' AS image_url,
                lb.latest_close, lb.bar_time,
                b24.close_24h,
                COALESCE(ac.cnt, 0) AS unresolved_anomalies
            FROM assets a
            LEFT JOIN latest_bars lb ON lb.asset_id = a.id
            LEFT JOIN bars_24h_ago b24 ON b24.asset_id = a.id
            LEFT JOIN anomaly_counts ac ON ac.asset_id = a.id
            WHERE (:active_only = false OR a.is_active = true)
              AND (:filter_class = false OR a.asset_class = :asset_class)
            ORDER BY
                CASE WHEN :sort_by = 'market_cap_rank' AND :sort_dir = 'asc'
                     THEN a.market_cap_rank END ASC NULLS LAST,
                CASE WHEN :sort_by = 'market_cap_rank' AND :sort_dir = 'desc'
                     THEN a.market_cap_rank END DESC NULLS LAST,
                CASE WHEN :sort_by = 'symbol' AND :sort_dir = 'asc'
                     THEN a.symbol END ASC,
                CASE WHEN :sort_by = 'symbol' AND :sort_dir = 'desc'
                     THEN a.symbol END DESC,
                CASE WHEN :sort_by = 'latest_price' AND :sort_dir = 'desc'
                     THEN lb.latest_close END DESC NULLS LAST,
                CASE WHEN :sort_by = 'latest_price' AND :sort_dir = 'asc'
                     THEN lb.latest_close END ASC NULLS LAST,
                CASE WHEN :sort_by = 'change_24h' AND :sort_dir = 'desc'
                     THEN CASE WHEN b24.close_24h > 0
                          THEN (lb.latest_close - b24.close_24h) / b24.close_24h
                          ELSE NULL END END DESC NULLS LAST,
                CASE WHEN :sort_by = 'change_24h' AND :sort_dir = 'asc'
                     THEN CASE WHEN b24.close_24h > 0
                          THEN (lb.latest_close - b24.close_24h) / b24.close_24h
                          ELSE NULL END END ASC NULLS LAST,
                a.market_cap_rank ASC NULLS LAST
            LIMIT :limit OFFSET :offset
        """),
        {
            "interval": PRICE_INTERVAL,
            "active_only": active_only,
            "filter_class": bool(asset_class),
            "asset_class": asset_class or "",
            "sort_by": sort_by,
            "sort_dir": sort_dir,
            "limit": limit,
            "offset": offset,
        },
    )
    rows = result.fetchall()

    items = []
    for r in rows:
        latest_price = None
        if r.latest_close is not None:
            change_pct = None
            if r.close_24h is not None and float(r.close_24h) > 0:
                change_pct = round(
                    (float(r.latest_close) - float(r.close_24h)) / float(r.close_24h) * 100, 2
                )
            latest_price = LatestPrice(
                close=float(r.latest_close),
                bar_time=r.bar_time,
                change_24h_pct=change_pct,
            )

        items.append(
            AssetListItem(
                id=r.id,
                symbol=r.symbol,
                name=r.name,
                asset_class=r.asset_class,
                market_cap_rank=r.market_cap_rank,
                is_active=r.is_active,
                image_url=r.image_url,
                latest_price=latest_price,
                unresolved_anomalies=r.unresolved_anomalies,
            )
        )

    log.debug("asset_list_query", total=total, returned=len(items), sort=sort_by)
    return items, total


async def get_latest_price(
    db: AsyncSession,
    asset_id: uuid.UUID,
    interval: str = PRICE_INTERVAL,
) -> LatestPrice | None:
    """Get latest price + 24h change for a single asset."""
    result = await db.execute(
        text("""
            WITH latest AS (
                SELECT "close", "time"
                FROM price_bars
                WHERE asset_id = :asset_id AND interval = :interval
                ORDER BY "time" DESC
                LIMIT 1
            ),
            ago_24h AS (
                SELECT "close"
                FROM price_bars
                WHERE asset_id = :asset_id AND interval = :interval
                  AND "time" <= (now() AT TIME ZONE 'UTC' - INTERVAL '24 hours')
                ORDER BY "time" DESC
                LIMIT 1
            )
            SELECT l."close" AS latest_close, l."time" AS bar_time,
                   a."close" AS close_24h
            FROM latest l
            LEFT JOIN ago_24h a ON true
        """),
        {"asset_id": asset_id, "interval": interval},
    )
    row = result.fetchone()
    if row is None or row.latest_close is None:
        return None

    change_pct = None
    if row.close_24h is not None and float(row.close_24h) > 0:
        change_pct = round(
            (float(row.latest_close) - float(row.close_24h)) / float(row.close_24h) * 100, 2
        )

    return LatestPrice(
        close=float(row.latest_close),
        bar_time=row.bar_time,
        change_24h_pct=change_pct,
    )


async def get_unresolved_anomaly_count(
    db: AsyncSession,
    asset_id: uuid.UUID,
) -> int:
    """Count unresolved anomalies for an asset."""
    result = await db.execute(
        select(func.count(AnomalyEvent.id)).where(
            and_(
                AnomalyEvent.asset_id == asset_id,
                AnomalyEvent.is_resolved.is_(False),
            )
        )
    )
    return result.scalar_one()

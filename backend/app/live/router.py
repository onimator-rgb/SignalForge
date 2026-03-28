"""Live prices endpoint — serves from in-memory cache with DB fallback."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.assets.service import get_latest_price
from app.database import get_db
from app.live.cache import LivePrice, get_all_prices, get_price
from app.logging_config import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/api/v1/live", tags=["live"])


def _freshness(updated_at: datetime) -> str:
    """Compute freshness label from last update time."""
    age_sec = (datetime.now(timezone.utc) - updated_at).total_seconds()
    if age_sec < 30:
        return "live"
    if age_sec < 120:
        return "recent"
    if age_sec < 600:
        return "delayed"
    return "stale"


@router.get("/prices")
async def live_prices(db: AsyncSession = Depends(get_db)):
    """Get latest prices for all active assets.

    Uses in-memory live cache when available, falls back to DB snapshot.
    """
    # Load active assets
    result = await db.execute(
        select(Asset.id, Asset.symbol, Asset.asset_class)
        .where(Asset.is_active.is_(True))
        .order_by(Asset.asset_class, Asset.symbol)
    )
    assets = result.all()
    now = datetime.now(timezone.utc)

    cache = get_all_prices()
    items = []
    live_count = 0
    fallback_count = 0

    for asset_id, symbol, asset_class in assets:
        cached = cache.get(symbol)
        if cached and (now - cached.updated_at).total_seconds() < 600:
            items.append({
                "asset_id": str(asset_id),
                "symbol": symbol,
                "asset_class": asset_class,
                "price": cached.price,
                "change_24h_pct": cached.change_24h_pct,
                "source": cached.source,
                "updated_at": cached.updated_at.isoformat(),
                "freshness": _freshness(cached.updated_at),
            })
            live_count += 1
        else:
            # DB fallback
            price_data = await get_latest_price(db, asset_id)
            if price_data:
                items.append({
                    "asset_id": str(asset_id),
                    "symbol": symbol,
                    "asset_class": asset_class,
                    "price": price_data.close,
                    "change_24h_pct": price_data.change_24h_pct,
                    "source": "db_snapshot",
                    "updated_at": price_data.bar_time.isoformat(),
                    "freshness": "delayed",
                })
                fallback_count += 1
            else:
                items.append({
                    "asset_id": str(asset_id),
                    "symbol": symbol,
                    "asset_class": asset_class,
                    "price": None,
                    "change_24h_pct": None,
                    "source": "none",
                    "updated_at": None,
                    "freshness": "unavailable",
                })

    if fallback_count > 0:
        log.debug("live_prices.fallback_used", count=fallback_count)

    return {
        "count": len(items),
        "live": live_count,
        "fallback": fallback_count,
        "items": items,
    }

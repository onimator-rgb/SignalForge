"""Live prices endpoints — REST snapshot + SSE push stream."""

import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.assets.service import get_latest_price
from app.database import get_db
from app.live.cache import (
    LivePrice, get_all_prices, get_price,
    subscribe, unsubscribe, subscriber_count,
)
from app.logging_config import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/api/v1/live", tags=["live"])

SSE_HEARTBEAT_SECONDS = 20


def _freshness(updated_at: datetime) -> str:
    age_sec = (datetime.now(timezone.utc) - updated_at).total_seconds()
    if age_sec < 30:
        return "live"
    if age_sec < 120:
        return "recent"
    if age_sec < 600:
        return "delayed"
    return "stale"


def _price_to_sse(p: LivePrice) -> str:
    """Format a LivePrice as SSE data line."""
    payload = json.dumps({
        "symbol": p.symbol,
        "asset_class": p.asset_class,
        "price": p.price,
        "change_24h_pct": p.change_24h_pct,
        "source": p.source,
        "freshness": _freshness(p.updated_at),
        "updated_at": p.updated_at.isoformat(),
    })
    return f"data: {payload}\n\n"


@router.get("/stream")
async def live_stream():
    """SSE stream of live price updates. Connect via EventSource."""

    async def event_generator():
        q = subscribe()
        log.info("live.sse_client_connect", subscribers=subscriber_count())
        try:
            while True:
                try:
                    price = await asyncio.wait_for(q.get(), timeout=SSE_HEARTBEAT_SECONDS)
                    yield _price_to_sse(price)
                except asyncio.TimeoutError:
                    # Heartbeat to keep connection alive
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            unsubscribe(q)
            log.info("live.sse_client_disconnect", subscribers=subscriber_count())

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/prices")
async def live_prices(db: AsyncSession = Depends(get_db)):
    """REST snapshot of latest prices (cache + DB fallback)."""
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

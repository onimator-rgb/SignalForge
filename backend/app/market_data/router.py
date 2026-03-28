"""Market data endpoints — inspect stored price bars."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.database import get_db
from app.ingestion.schemas import PriceBarOut
from app.market_data.models import PriceBar

router = APIRouter(prefix="/api/v1", tags=["market_data"])


@router.get("/assets/{asset_id}/ohlcv", response_model=list[PriceBarOut])
async def get_ohlcv(
    asset_id: UUID,
    interval: str = Query("1h", description="Bar interval: 5m, 1h, 1d"),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """Get OHLCV bars for an asset, most recent first."""
    result = await db.execute(
        select(PriceBar)
        .where(PriceBar.asset_id == asset_id, PriceBar.interval == interval)
        .order_by(PriceBar.time.desc())
        .limit(limit)
    )
    bars = result.scalars().all()
    return [PriceBarOut.model_validate(b) for b in bars]


@router.get("/price-bars/count")
async def price_bar_counts(
    db: AsyncSession = Depends(get_db),
):
    """Quick summary: how many bars per asset per interval."""
    result = await db.execute(
        text("""
            SELECT a.symbol, pb.interval, count(*) as bar_count,
                   min(pb.time) as earliest, max(pb.time) as latest
            FROM price_bars pb
            JOIN assets a ON a.id = pb.asset_id
            GROUP BY a.symbol, pb.interval
            ORDER BY a.symbol, pb.interval
        """)
    )
    rows = result.fetchall()
    return [
        {
            "symbol": r.symbol,
            "interval": r.interval,
            "bar_count": r.bar_count,
            "earliest": r.earliest.isoformat() if r.earliest else None,
            "latest": r.latest.isoformat() if r.latest else None,
        }
        for r in rows
    ]

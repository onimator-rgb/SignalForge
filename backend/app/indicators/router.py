"""Indicator endpoints — on-the-fly technical analysis."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.database import get_db
from app.indicators.schemas import IndicatorHistory, IndicatorSnapshot, MultiTimeframeIndicators
from app.indicators.service import get_indicator_history, get_indicators, get_multi_timeframe_indicators

router = APIRouter(prefix="/api/v1", tags=["indicators"])


@router.get("/assets/{asset_id}/indicators", response_model=IndicatorSnapshot)
async def asset_indicators(
    asset_id: UUID,
    interval: str = Query("1h", description="Bar interval: 5m, 1h, 1d"),
    db: AsyncSession = Depends(get_db),
):
    """Get current technical indicators for an asset.

    Computed on-the-fly from stored price bars.
    Returns RSI-14, MACD(12,26,9), and Bollinger Bands(20,2).
    """
    # Verify asset exists
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    snapshot = await get_indicators(
        db=db,
        asset_id=asset_id,
        asset_symbol=asset.symbol,
        interval=interval,
    )
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail=f"No price bars available for {asset.symbol} interval={interval}",
        )

    return snapshot


ALLOWED_INTERVALS = {"1m", "5m", "15m", "1h", "4h", "1d"}


@router.get("/assets/{asset_id}/indicators/mtf", response_model=MultiTimeframeIndicators)
async def get_mtf_indicators(
    asset_id: UUID,
    intervals: str = Query(default="5m,1h,4h,1d", description="Comma-separated intervals"),
    db: AsyncSession = Depends(get_db),
) -> MultiTimeframeIndicators:
    """Get indicators across multiple timeframes in a single call."""
    interval_list = [s.strip() for s in intervals.split(",")]
    invalid = [iv for iv in interval_list if iv not in ALLOWED_INTERVALS]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid intervals: {invalid}. Allowed: {sorted(ALLOWED_INTERVALS)}",
        )

    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    from datetime import datetime, timezone

    timeframes = await get_multi_timeframe_indicators(
        db=db,
        asset_id=asset_id,
        asset_symbol=asset.symbol,
        intervals=interval_list,
    )
    return MultiTimeframeIndicators(
        asset_id=asset_id,
        timeframes=timeframes,
        computed_at=datetime.now(tz=timezone.utc),
    )


@router.get("/assets/{asset_id}/indicators/history", response_model=IndicatorHistory)
async def asset_indicator_history(
    asset_id: UUID,
    interval: str = Query("1h", description="Bar interval: 5m, 1h, 1d"),
    db: AsyncSession = Depends(get_db),
) -> IndicatorHistory:
    """Get rolling indicator history (RSI, MACD histogram, ADX) for sparkline display."""
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    history = await get_indicator_history(
        db=db,
        asset_id=asset_id,
        asset_symbol=asset.symbol,
        interval=interval,
    )
    if history is None:
        raise HTTPException(
            status_code=404,
            detail=f"No price bars available for {asset.symbol} interval={interval}",
        )

    return history

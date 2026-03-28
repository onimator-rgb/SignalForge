"""Indicator endpoints — on-the-fly technical analysis."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.database import get_db
from app.indicators.schemas import IndicatorSnapshot
from app.indicators.service import get_indicators

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

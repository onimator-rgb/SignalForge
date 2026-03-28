"""Asset endpoints — list, detail, search."""

from enum import Enum
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.assets.schemas import (
    AssetDetail,
    AssetIndicatorsSummary,
    AssetListItem,
    AssetSearchResult,
)
from app.assets.service import (
    get_asset_list,
    get_latest_price,
    get_unresolved_anomaly_count,
)
from app.core.schemas import PaginatedResponse
from app.database import get_db
from app.indicators.service import get_indicators
from app.logging_config import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/api/v1/assets", tags=["assets"])

VALID_SORT_FIELDS = {"market_cap_rank", "symbol", "latest_price", "change_24h"}
VALID_SORT_DIRS = {"asc", "desc"}


@router.get("", response_model=PaginatedResponse[AssetListItem])
async def list_assets(
    active_only: bool = Query(True, description="Filter to active assets only"),
    asset_class: str | None = Query(None, description="Filter by asset_class: crypto, stock"),
    sort_by: str = Query("market_cap_rank", description="Sort field: market_cap_rank, symbol, latest_price, change_24h"),
    sort_dir: str = Query("asc", description="Sort direction: asc, desc"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List assets with latest price, 24h change, and anomaly counts."""
    if sort_by not in VALID_SORT_FIELDS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid sort_by: {sort_by}. Valid: {', '.join(VALID_SORT_FIELDS)}",
        )
    if sort_dir not in VALID_SORT_DIRS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid sort_dir: {sort_dir}. Valid: asc, desc",
        )

    items, total = await get_asset_list(
        db=db,
        active_only=active_only,
        asset_class=asset_class,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/search", response_model=list[AssetSearchResult])
async def search_assets(
    q: str = Query(..., min_length=1, max_length=50, description="Search query"),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Search assets by symbol or name. Returns compact results for autocomplete."""
    pattern = f"%{q.strip().upper()}%"
    result = await db.execute(
        select(Asset)
        .where(
            Asset.is_active.is_(True),
            or_(
                Asset.symbol.ilike(pattern),
                Asset.name.ilike(pattern),
            ),
        )
        .order_by(Asset.market_cap_rank.asc().nulls_last())
        .limit(limit)
    )
    assets = result.scalars().all()
    log.debug("asset_search", query=q, results=len(assets))

    return [
        AssetSearchResult(
            id=a.id,
            symbol=a.symbol,
            name=a.name,
            market_cap_rank=a.market_cap_rank,
            image_url=a.metadata_.get("image") if a.metadata_ else None,
        )
        for a in assets
    ]


@router.get("/{asset_id}", response_model=AssetDetail)
async def get_asset(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get full asset detail with latest price, indicators, and anomaly count."""
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    log.debug("asset_detail", symbol=asset.symbol)

    # Latest price + 24h change
    latest_price = await get_latest_price(db, asset_id)

    # Indicators (on-the-fly, cheap for a single asset)
    indicators_summary = None
    ind = await get_indicators(db, asset_id, asset.symbol, interval="1h")
    if ind is not None:
        indicators_summary = AssetIndicatorsSummary(
            interval=ind.interval,
            bar_time=ind.bar_time,
            rsi_14=ind.rsi_14,
            macd=ind.macd,
            bollinger=ind.bollinger,
        )

    # Anomaly count
    anomaly_count = await get_unresolved_anomaly_count(db, asset_id)

    return AssetDetail(
        id=asset.id,
        symbol=asset.symbol,
        name=asset.name,
        provider_symbol=asset.provider_symbol,
        asset_class=asset.asset_class,
        exchange=asset.exchange,
        currency=asset.currency,
        coingecko_id=asset.coingecko_id,
        market_cap_rank=asset.market_cap_rank,
        is_active=asset.is_active,
        image_url=asset.metadata_.get("image") if asset.metadata_ else None,
        metadata=asset.metadata_ or {},
        latest_price=latest_price,
        indicators=indicators_summary,
        unresolved_anomalies=anomaly_count,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
    )

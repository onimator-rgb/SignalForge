"""Watchlist endpoints — CRUD + asset membership."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.database import get_db
from app.logging_config import get_logger
from app.watchlists.models import Watchlist, WatchlistAsset
from app.watchlists.schemas import (
    AddAssetRequest,
    CreateWatchlistRequest,
    UpdateWatchlistRequest,
    WatchlistAssetOut,
    WatchlistOut,
)

log = get_logger(__name__)

router = APIRouter(prefix="/api/v1/watchlists", tags=["watchlists"])


# ── Helpers ───────────────────────────────────────

async def _watchlist_out(db: AsyncSession, wl: Watchlist) -> WatchlistOut:
    count_res = await db.execute(
        select(func.count()).where(WatchlistAsset.watchlist_id == wl.id)
    )
    return WatchlistOut(
        id=wl.id,
        name=wl.name,
        description=wl.description,
        asset_count=count_res.scalar_one(),
        created_at=wl.created_at,
        updated_at=wl.updated_at,
    )


async def _get_watchlist_or_404(db: AsyncSession, wl_id: UUID) -> Watchlist:
    result = await db.execute(select(Watchlist).where(Watchlist.id == wl_id))
    wl = result.scalar_one_or_none()
    if not wl:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    return wl


# ── Watchlist CRUD ────────────────────────────────

@router.get("", response_model=list[WatchlistOut])
async def list_watchlists(db: AsyncSession = Depends(get_db)):
    """List all watchlists with asset counts."""
    result = await db.execute(
        select(
            Watchlist,
            func.count(WatchlistAsset.asset_id).label("asset_count"),
        )
        .outerjoin(WatchlistAsset, Watchlist.id == WatchlistAsset.watchlist_id)
        .group_by(Watchlist.id)
        .order_by(Watchlist.created_at.desc())
    )
    return [
        WatchlistOut(
            id=row.Watchlist.id,
            name=row.Watchlist.name,
            description=row.Watchlist.description,
            asset_count=row.asset_count,
            created_at=row.Watchlist.created_at,
            updated_at=row.Watchlist.updated_at,
        )
        for row in result.all()
    ]


@router.post("", response_model=WatchlistOut, status_code=201)
async def create_watchlist(req: CreateWatchlistRequest, db: AsyncSession = Depends(get_db)):
    """Create a new watchlist."""
    wl = Watchlist(name=req.name, description=req.description)
    db.add(wl)
    await db.commit()
    await db.refresh(wl)
    log.info("watchlist.create_done", id=str(wl.id), name=wl.name)
    return await _watchlist_out(db, wl)


@router.get("/{watchlist_id}", response_model=WatchlistOut)
async def get_watchlist(watchlist_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get watchlist details."""
    wl = await _get_watchlist_or_404(db, watchlist_id)
    return await _watchlist_out(db, wl)


@router.patch("/{watchlist_id}", response_model=WatchlistOut)
async def update_watchlist(
    watchlist_id: UUID, req: UpdateWatchlistRequest, db: AsyncSession = Depends(get_db)
):
    """Update watchlist name or description."""
    wl = await _get_watchlist_or_404(db, watchlist_id)
    if req.name is not None:
        wl.name = req.name
    if req.description is not None:
        wl.description = req.description
    wl.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(wl)
    log.info("watchlist.update_done", id=str(wl.id), name=wl.name)
    return await _watchlist_out(db, wl)


@router.delete("/{watchlist_id}", status_code=204)
async def delete_watchlist(watchlist_id: UUID, db: AsyncSession = Depends(get_db)):
    """Delete a watchlist and its memberships."""
    wl = await _get_watchlist_or_404(db, watchlist_id)
    await db.delete(wl)
    await db.commit()
    log.info("watchlist.delete_done", id=str(watchlist_id))


# ── Asset membership ─────────────────────────────

@router.get("/{watchlist_id}/assets", response_model=list[WatchlistAssetOut])
async def list_watchlist_assets(watchlist_id: UUID, db: AsyncSession = Depends(get_db)):
    """List assets in a watchlist with enriched data (price, recommendation, portfolio)."""
    await _get_watchlist_or_404(db, watchlist_id)

    from app.assets.service import get_latest_price
    from app.recommendations.models import Recommendation
    from app.portfolio.models import PortfolioPosition

    # Base asset data
    result = await db.execute(
        select(
            WatchlistAsset.asset_id,
            WatchlistAsset.added_at,
            Asset.symbol,
            Asset.name,
            Asset.asset_class,
            Asset.metadata_.label("metadata"),
        )
        .join(Asset, WatchlistAsset.asset_id == Asset.id)
        .where(WatchlistAsset.watchlist_id == watchlist_id)
        .order_by(Asset.symbol)
    )
    rows = result.all()

    # Batch: active recommendations
    asset_ids = [r.asset_id for r in rows]
    rec_res = await db.execute(
        select(Recommendation.asset_id, Recommendation.recommendation_type, Recommendation.score)
        .where(Recommendation.asset_id.in_(asset_ids), Recommendation.status == "active")
    )
    rec_map = {r.asset_id: (r.recommendation_type, float(r.score)) for r in rec_res.all()}

    # Batch: open portfolio positions
    pos_res = await db.execute(
        select(PortfolioPosition.asset_id)
        .where(PortfolioPosition.asset_id.in_(asset_ids), PortfolioPosition.status == "open")
    )
    in_portfolio = set(r[0] for r in pos_res.all())

    items = []
    for row in rows:
        price_data = await get_latest_price(db, row.asset_id)
        rec = rec_map.get(row.asset_id)
        items.append(
            WatchlistAssetOut(
                asset_id=row.asset_id,
                symbol=row.symbol,
                name=row.name,
                asset_class=row.asset_class,
                image_url=row.metadata.get("image") if row.metadata else None,
                added_at=row.added_at,
                latest_price=price_data.close if price_data else None,
                change_24h_pct=price_data.change_24h_pct if price_data else None,
                rec_type=rec[0] if rec else None,
                rec_score=rec[1] if rec else None,
                in_portfolio=row.asset_id in in_portfolio,
            )
        )
    return items


@router.post("/{watchlist_id}/assets", status_code=201)
async def add_asset(
    watchlist_id: UUID, req: AddAssetRequest, db: AsyncSession = Depends(get_db)
):
    """Add an asset to a watchlist."""
    await _get_watchlist_or_404(db, watchlist_id)

    # Check asset exists
    asset_res = await db.execute(select(Asset).where(Asset.id == req.asset_id))
    if not asset_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Asset not found")

    # Check duplicate
    existing = await db.execute(
        select(WatchlistAsset).where(
            WatchlistAsset.watchlist_id == watchlist_id,
            WatchlistAsset.asset_id == req.asset_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Asset already in watchlist")

    wa = WatchlistAsset(watchlist_id=watchlist_id, asset_id=req.asset_id)
    db.add(wa)
    await db.commit()
    log.info("watchlist.asset_add_done", watchlist_id=str(watchlist_id), asset_id=str(req.asset_id))
    return {"status": "ok"}


@router.delete("/{watchlist_id}/assets/{asset_id}", status_code=204)
async def remove_asset(
    watchlist_id: UUID, asset_id: UUID, db: AsyncSession = Depends(get_db)
):
    """Remove an asset from a watchlist."""
    result = await db.execute(
        delete(WatchlistAsset).where(
            WatchlistAsset.watchlist_id == watchlist_id,
            WatchlistAsset.asset_id == asset_id,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Asset not in watchlist")
    await db.commit()
    log.info("watchlist.asset_remove_done", watchlist_id=str(watchlist_id), asset_id=str(asset_id))

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


# ── Intelligence / recommendations ────────────────

@router.get("/{watchlist_id}/intelligence")
async def watchlist_intelligence(watchlist_id: UUID, db: AsyncSession = Depends(get_db)):
    """Quick intelligence summary for a watchlist."""
    wl = await _get_watchlist_or_404(db, watchlist_id)

    from app.recommendations.models import Recommendation
    from app.portfolio.models import PortfolioPosition
    from app.anomalies.models import AnomalyEvent

    # Asset IDs in watchlist
    wa_res = await db.execute(
        select(WatchlistAsset.asset_id).where(WatchlistAsset.watchlist_id == watchlist_id)
    )
    asset_ids = [r[0] for r in wa_res.all()]
    if not asset_ids:
        return {"watchlist": wl.name, "total_assets": 0, "signals": {}, "strongest": [], "weakest": []}

    # Class counts
    class_res = await db.execute(
        select(Asset.asset_class, func.count()).where(Asset.id.in_(asset_ids)).group_by(Asset.asset_class)
    )
    class_counts: dict[str, int] = dict(class_res.all())  # type: ignore[arg-type]

    # Recommendation counts
    rec_res = await db.execute(
        select(
            Recommendation.asset_id, Recommendation.recommendation_type,
            Recommendation.score, Asset.symbol,
        )
        .join(Asset, Recommendation.asset_id == Asset.id)
        .where(Recommendation.asset_id.in_(asset_ids), Recommendation.status == "active")
        .order_by(Recommendation.score.desc())
    )
    recs = rec_res.all()
    rec_type_counts: dict[str, int] = {}
    for r in recs:
        rec_type_counts[r.recommendation_type] = rec_type_counts.get(r.recommendation_type, 0) + 1

    # Portfolio overlap
    pos_res = await db.execute(
        select(func.count()).where(
            PortfolioPosition.asset_id.in_(asset_ids), PortfolioPosition.status == "open"
        )
    )
    open_positions = pos_res.scalar_one()

    # Anomaly count
    anom_res = await db.execute(
        select(func.count()).where(
            AnomalyEvent.asset_id.in_(asset_ids), AnomalyEvent.is_resolved.is_(False)
        )
    )
    unresolved_anomalies = anom_res.scalar_one()

    strongest = [{"symbol": r.symbol, "score": float(r.score), "type": r.recommendation_type} for r in recs[:3]]
    weakest = [{"symbol": r.symbol, "score": float(r.score), "type": r.recommendation_type} for r in recs[-3:]] if len(recs) > 3 else []

    log.info("watchlist.intelligence_fetch_done", watchlist_id=str(watchlist_id), assets=len(asset_ids))

    return {
        "watchlist": wl.name,
        "total_assets": len(asset_ids),
        "crypto_count": class_counts.get("crypto", 0),
        "stock_count": class_counts.get("stock", 0),
        "signals": rec_type_counts,
        "candidate_buy_count": rec_type_counts.get("candidate_buy", 0),
        "avoid_count": rec_type_counts.get("avoid", 0),
        "open_positions": open_positions,
        "unresolved_anomalies": unresolved_anomalies,
        "strongest": strongest,
        "weakest": weakest,
    }


@router.get("/{watchlist_id}/recommendations")
async def watchlist_recommendations(watchlist_id: UUID, db: AsyncSession = Depends(get_db)):
    """Active recommendations for assets in a watchlist."""
    await _get_watchlist_or_404(db, watchlist_id)

    from app.recommendations.models import Recommendation

    wa_res = await db.execute(
        select(WatchlistAsset.asset_id).where(WatchlistAsset.watchlist_id == watchlist_id)
    )
    asset_ids = [r[0] for r in wa_res.all()]
    if not asset_ids:
        return []

    result = await db.execute(
        select(
            Recommendation.id, Recommendation.asset_id, Recommendation.recommendation_type,
            Recommendation.score, Recommendation.confidence, Recommendation.risk_level,
            Recommendation.rationale_summary, Recommendation.generated_at,
            Asset.symbol, Asset.asset_class,
        )
        .join(Asset, Recommendation.asset_id == Asset.id)
        .where(Recommendation.asset_id.in_(asset_ids), Recommendation.status == "active")
        .order_by(Recommendation.score.desc())
    )

    log.info("watchlist.recommendations_fetch_done", watchlist_id=str(watchlist_id))

    return [
        {
            "id": str(r.id), "asset_id": str(r.asset_id), "symbol": r.symbol,
            "asset_class": r.asset_class, "recommendation_type": r.recommendation_type,
            "score": float(r.score), "confidence": r.confidence, "risk_level": r.risk_level,
            "rationale_summary": r.rationale_summary, "generated_at": r.generated_at,
        }
        for r in result.all()
    ]


# ── Anomalies ─────────────────────────────────────

@router.get("/{watchlist_id}/anomalies")
async def watchlist_anomalies(watchlist_id: UUID, db: AsyncSession = Depends(get_db)):
    """Return unresolved anomalies (score >= 0.5) from the last 24 h for watchlist assets."""
    from datetime import timedelta

    from app.anomalies.models import AnomalyEvent

    await _get_watchlist_or_404(db, watchlist_id)

    wa_res = await db.execute(
        select(WatchlistAsset.asset_id, Asset.symbol)
        .join(Asset, WatchlistAsset.asset_id == Asset.id)
        .where(WatchlistAsset.watchlist_id == watchlist_id)
    )
    wa_rows = wa_res.all()
    asset_ids = [r.asset_id for r in wa_rows]

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)

    anomalies: list[dict] = []
    if asset_ids:
        anom_res = await db.execute(
            select(AnomalyEvent, Asset.symbol)
            .join(Asset, AnomalyEvent.asset_id == Asset.id)
            .where(
                AnomalyEvent.asset_id.in_(asset_ids),
                AnomalyEvent.is_resolved.is_(False),
                AnomalyEvent.detected_at >= cutoff,
                AnomalyEvent.score >= 0.5,
            )
            .order_by(AnomalyEvent.score.desc())
        )
        for row in anom_res.all():
            anomalies.append(
                {
                    "id": str(row.AnomalyEvent.id),
                    "asset_id": str(row.AnomalyEvent.asset_id),
                    "symbol": row.symbol,
                    "anomaly_type": row.AnomalyEvent.anomaly_type,
                    "severity": row.AnomalyEvent.severity,
                    "score": float(row.AnomalyEvent.score),
                    "detected_at": row.AnomalyEvent.detected_at.isoformat(),
                    "details": row.AnomalyEvent.details,
                }
            )

    log.info("watchlist.anomalies_fetch_done", watchlist_id=str(watchlist_id), total=len(anomalies))
    return {
        "watchlist_id": str(watchlist_id),
        "assets": [r.symbol for r in wa_rows],
        "anomalies": anomalies,
        "last_updated": now.isoformat(),
        "total": len(anomalies),
    }


# ── Asset membership ─────────────────────────────

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
    if result.rowcount == 0:  # type: ignore[attr-defined]
        raise HTTPException(status_code=404, detail="Asset not in watchlist")
    await db.commit()
    log.info("watchlist.asset_remove_done", watchlist_id=str(watchlist_id), asset_id=str(asset_id))

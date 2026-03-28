"""Recommendation endpoints — list, active, detail, by asset."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.core.schemas import PaginatedResponse
from app.database import get_db
from app.recommendations.models import Recommendation
from app.recommendations.schemas import RecommendationOut

router = APIRouter(prefix="/api/v1/recommendations", tags=["recommendations"])


def _rec_out(rec: Recommendation, symbol: str | None, asset_class: str | None) -> RecommendationOut:
    return RecommendationOut(
        id=rec.id,
        asset_id=rec.asset_id,
        asset_symbol=symbol,
        asset_class=asset_class,
        generated_at=rec.generated_at,
        recommendation_type=rec.recommendation_type,
        score=float(rec.score),
        confidence=rec.confidence,
        risk_level=rec.risk_level,
        rationale_summary=rec.rationale_summary,
        signal_breakdown=rec.signal_breakdown,
        entry_price_snapshot=float(rec.entry_price_snapshot) if rec.entry_price_snapshot else None,
        time_horizon=rec.time_horizon,
        valid_until=rec.valid_until,
        status=rec.status,
        created_at=rec.created_at,
    )


@router.get("", response_model=PaginatedResponse[RecommendationOut])
async def list_recommendations(
    asset_class: str | None = Query(None),
    recommendation_type: str | None = Query(None),
    status: str | None = Query(None, description="active, expired, superseded"),
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List recommendations, newest first."""
    conditions = []
    if asset_class:
        conditions.append(Asset.asset_class == asset_class)
    if recommendation_type:
        conditions.append(Recommendation.recommendation_type == recommendation_type)
    if status:
        conditions.append(Recommendation.status == status)
    where = and_(*conditions) if conditions else True

    count_q = (
        select(func.count(Recommendation.id))
        .join(Asset, Recommendation.asset_id == Asset.id)
        .where(where)
    )
    total = (await db.execute(count_q)).scalar_one()

    result = await db.execute(
        select(Recommendation, Asset.symbol, Asset.asset_class)
        .join(Asset, Recommendation.asset_id == Asset.id)
        .where(where)
        .order_by(Recommendation.generated_at.desc())
        .limit(limit).offset(offset)
    )

    items = [_rec_out(row.Recommendation, row.symbol, row.asset_class) for row in result.all()]
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/active", response_model=list[RecommendationOut])
async def list_active(
    asset_class: str | None = Query(None),
    min_score: float | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List only active recommendations, sorted by score descending."""
    conditions = [Recommendation.status == "active"]
    if asset_class:
        conditions.append(Asset.asset_class == asset_class)
    if min_score is not None:
        conditions.append(Recommendation.score >= min_score)

    result = await db.execute(
        select(Recommendation, Asset.symbol, Asset.asset_class)
        .join(Asset, Recommendation.asset_id == Asset.id)
        .where(and_(*conditions))
        .order_by(Recommendation.score.desc())
    )

    return [_rec_out(row.Recommendation, row.symbol, row.asset_class) for row in result.all()]


@router.get("/{recommendation_id}", response_model=RecommendationOut)
async def get_recommendation(recommendation_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a single recommendation with full details."""
    result = await db.execute(
        select(Recommendation, Asset.symbol, Asset.asset_class)
        .join(Asset, Recommendation.asset_id == Asset.id)
        .where(Recommendation.id == recommendation_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return _rec_out(row.Recommendation, row.symbol, row.asset_class)

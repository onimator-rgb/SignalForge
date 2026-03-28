"""Anomaly endpoints — list, filter, inspect anomaly events."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.anomalies.models import AnomalyEvent
from app.anomalies.schemas import AnomalyEventOut, AnomalyStatsOut
from app.assets.models import Asset
from app.core.schemas import PaginatedResponse
from app.database import get_db

router = APIRouter(prefix="/api/v1", tags=["anomalies"])


@router.get("/anomalies", response_model=PaginatedResponse[AnomalyEventOut])
async def list_anomalies(
    asset_id: UUID | None = Query(None),
    severity: str | None = Query(None, description="low, medium, high, critical"),
    anomaly_type: str | None = Query(None, description="price_spike, price_crash, volume_spike, rsi_extreme"),
    is_resolved: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List anomaly events with optional filters."""
    conditions = []
    if asset_id is not None:
        conditions.append(AnomalyEvent.asset_id == asset_id)
    if severity is not None:
        conditions.append(AnomalyEvent.severity == severity)
    if anomaly_type is not None:
        conditions.append(AnomalyEvent.anomaly_type == anomaly_type)
    if is_resolved is not None:
        conditions.append(AnomalyEvent.is_resolved.is_(is_resolved))

    where = and_(*conditions) if conditions else True

    # Total count
    count_result = await db.execute(
        select(func.count(AnomalyEvent.id)).where(where)
    )
    total = count_result.scalar_one()

    # Fetch page, join asset for symbol
    result = await db.execute(
        select(AnomalyEvent, Asset.symbol)
        .join(Asset, AnomalyEvent.asset_id == Asset.id)
        .where(where)
        .order_by(AnomalyEvent.detected_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = [
        AnomalyEventOut(
            id=event.id,
            asset_id=event.asset_id,
            asset_symbol=symbol,
            detected_at=event.detected_at,
            anomaly_type=event.anomaly_type,
            severity=event.severity,
            score=float(event.score),
            details=event.details,
            timeframe=event.timeframe,
            is_resolved=event.is_resolved,
            resolved_at=event.resolved_at,
            created_at=event.created_at,
        )
        for event, symbol in result.all()
    ]

    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/anomalies/stats", response_model=AnomalyStatsOut)
async def anomaly_stats(
    db: AsyncSession = Depends(get_db),
):
    """Aggregate anomaly statistics."""
    # Total
    total_res = await db.execute(select(func.count(AnomalyEvent.id)))
    total = total_res.scalar_one()

    # Unresolved
    unresolved_res = await db.execute(
        select(func.count(AnomalyEvent.id)).where(AnomalyEvent.is_resolved.is_(False))
    )
    unresolved = unresolved_res.scalar_one()

    # By severity
    sev_res = await db.execute(
        select(AnomalyEvent.severity, func.count(AnomalyEvent.id))
        .group_by(AnomalyEvent.severity)
    )
    by_severity = {row[0]: row[1] for row in sev_res.all()}

    # By type
    type_res = await db.execute(
        select(AnomalyEvent.anomaly_type, func.count(AnomalyEvent.id))
        .group_by(AnomalyEvent.anomaly_type)
    )
    by_type = {row[0]: row[1] for row in type_res.all()}

    return AnomalyStatsOut(
        total=total,
        unresolved=unresolved,
        by_severity=by_severity,
        by_type=by_type,
    )


@router.get("/assets/{asset_id}/anomalies", response_model=list[AnomalyEventOut])
async def asset_anomalies(
    asset_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List anomalies for a specific asset, most recent first."""
    result = await db.execute(
        select(AnomalyEvent, Asset.symbol)
        .join(Asset, AnomalyEvent.asset_id == Asset.id)
        .where(AnomalyEvent.asset_id == asset_id)
        .order_by(AnomalyEvent.detected_at.desc())
        .limit(limit)
    )
    return [
        AnomalyEventOut(
            id=event.id,
            asset_id=event.asset_id,
            asset_symbol=symbol,
            detected_at=event.detected_at,
            anomaly_type=event.anomaly_type,
            severity=event.severity,
            score=float(event.score),
            details=event.details,
            timeframe=event.timeframe,
            is_resolved=event.is_resolved,
            resolved_at=event.resolved_at,
            created_at=event.created_at,
        )
        for event, symbol in result.all()
    ]

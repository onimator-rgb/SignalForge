"""Alert endpoints — rules CRUD, events list, mark read, stats."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.models import AlertEvent, AlertRule
from app.alerts.schemas import (
    AlertEventOut, AlertRuleOut, AlertStatsOut,
    CreateAlertRuleRequest, UpdateAlertRuleRequest,
)
from app.alerts.service import VALID_RULE_TYPES
from app.assets.models import Asset
from app.core.schemas import PaginatedResponse
from app.database import get_db

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


# --- Rules ---

@router.get("/rules", response_model=list[AlertRuleOut])
async def list_rules(db: AsyncSession = Depends(get_db)):
    """List all alert rules."""
    result = await db.execute(
        select(AlertRule, Asset.symbol)
        .outerjoin(Asset, AlertRule.asset_id == Asset.id)
        .order_by(AlertRule.created_at.desc())
    )
    return [
        AlertRuleOut(
            **{c.key: getattr(rule, c.key) for c in AlertRule.__table__.columns},
            asset_symbol=symbol,
        )
        for rule, symbol in result.all()
    ]


@router.post("/rules", response_model=AlertRuleOut, status_code=201)
async def create_rule(req: CreateAlertRuleRequest, db: AsyncSession = Depends(get_db)):
    """Create a new alert rule."""
    if req.rule_type not in VALID_RULE_TYPES:
        raise HTTPException(status_code=422, detail=f"Invalid rule_type. Valid: {', '.join(VALID_RULE_TYPES)}")

    # Validate condition
    if req.rule_type in ("price_above", "price_below") and "threshold" not in req.condition:
        raise HTTPException(status_code=422, detail="condition must include 'threshold' for price rules")
    if req.rule_type == "anomaly_severity_min" and "severity_min" not in req.condition:
        raise HTTPException(status_code=422, detail="condition must include 'severity_min'")

    rule = AlertRule(
        asset_id=req.asset_id,
        name=req.name,
        rule_type=req.rule_type,
        condition=req.condition,
        cooldown_minutes=req.cooldown_minutes,
        is_active=req.is_active,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)

    # Get asset symbol if linked
    symbol = None
    if rule.asset_id:
        res = await db.execute(select(Asset.symbol).where(Asset.id == rule.asset_id))
        symbol = res.scalar_one_or_none()

    return AlertRuleOut(
        **{c.key: getattr(rule, c.key) for c in AlertRule.__table__.columns},
        asset_symbol=symbol,
    )


@router.patch("/rules/{rule_id}", response_model=AlertRuleOut)
async def update_rule(rule_id: UUID, req: UpdateAlertRuleRequest, db: AsyncSession = Depends(get_db)):
    """Update an existing alert rule."""
    result = await db.execute(select(AlertRule).where(AlertRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    if req.name is not None:
        rule.name = req.name
    if req.condition is not None:
        rule.condition = req.condition
    if req.cooldown_minutes is not None:
        rule.cooldown_minutes = req.cooldown_minutes
    if req.is_active is not None:
        rule.is_active = req.is_active

    await db.commit()
    await db.refresh(rule)

    symbol = None
    if rule.asset_id:
        res = await db.execute(select(Asset.symbol).where(Asset.id == rule.asset_id))
        symbol = res.scalar_one_or_none()

    return AlertRuleOut(
        **{c.key: getattr(rule, c.key) for c in AlertRule.__table__.columns},
        asset_symbol=symbol,
    )


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_rule(rule_id: UUID, db: AsyncSession = Depends(get_db)):
    """Delete an alert rule."""
    result = await db.execute(select(AlertRule).where(AlertRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    await db.delete(rule)
    await db.commit()


# --- Events ---

@router.get("/events", response_model=PaginatedResponse[AlertEventOut])
async def list_events(
    is_read: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List alert events, newest first."""
    from sqlalchemy import and_

    conditions = []
    if is_read is not None:
        conditions.append(AlertEvent.is_read.is_(is_read))
    where = and_(*conditions) if conditions else True

    count_res = await db.execute(select(func.count(AlertEvent.id)).where(where))
    total = count_res.scalar_one()

    result = await db.execute(
        select(AlertEvent, AlertRule.name.label("rule_name"), Asset.symbol.label("asset_symbol"))
        .join(AlertRule, AlertEvent.alert_rule_id == AlertRule.id)
        .outerjoin(Asset, AlertEvent.asset_id == Asset.id)
        .where(where)
        .order_by(AlertEvent.triggered_at.desc())
        .limit(limit).offset(offset)
    )

    items = [
        AlertEventOut(
            id=row.AlertEvent.id,
            alert_rule_id=row.AlertEvent.alert_rule_id,
            rule_name=row.rule_name,
            anomaly_event_id=row.AlertEvent.anomaly_event_id,
            asset_id=row.AlertEvent.asset_id,
            asset_symbol=row.asset_symbol,
            triggered_at=row.AlertEvent.triggered_at,
            message=row.AlertEvent.message,
            details=row.AlertEvent.details,
            is_read=row.AlertEvent.is_read,
            created_at=row.AlertEvent.created_at,
        )
        for row in result.all()
    ]

    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.patch("/events/{event_id}/read")
async def mark_read(event_id: UUID, db: AsyncSession = Depends(get_db)):
    """Mark an alert event as read."""
    result = await db.execute(select(AlertEvent).where(AlertEvent.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    event.is_read = True
    await db.commit()
    return {"status": "ok", "event_id": str(event_id)}


@router.post("/events/read-all")
async def mark_all_read(db: AsyncSession = Depends(get_db)):
    """Mark all unread alert events as read."""
    from sqlalchemy import update
    result = await db.execute(
        update(AlertEvent).where(AlertEvent.is_read.is_(False)).values(is_read=True)
    )
    await db.commit()
    return {"status": "ok", "marked": result.rowcount}


# --- Stats ---

@router.get("/stats", response_model=AlertStatsOut)
async def alert_stats(db: AsyncSession = Depends(get_db)):
    """Alert statistics."""
    total_events_res = await db.execute(select(func.count(AlertEvent.id)))
    unread_res = await db.execute(
        select(func.count(AlertEvent.id)).where(AlertEvent.is_read.is_(False))
    )
    total_rules_res = await db.execute(select(func.count(AlertRule.id)))
    active_rules_res = await db.execute(
        select(func.count(AlertRule.id)).where(AlertRule.is_active.is_(True))
    )
    return AlertStatsOut(
        total_events=total_events_res.scalar_one(),
        unread_events=unread_res.scalar_one(),
        total_rules=total_rules_res.scalar_one(),
        active_rules=active_rules_res.scalar_one(),
    )

"""Alert evaluation service — checks rules against current data, creates events."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.models import AlertEvent, AlertRule
from app.anomalies.models import AnomalyEvent
from app.assets.service import get_latest_price
from app.logging_config import get_logger

log = get_logger(__name__)

VALID_RULE_TYPES = {"price_above", "price_below", "anomaly_detected", "anomaly_severity_min"}
SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


async def evaluate_alerts_after_ingestion(
    db: AsyncSession,
    ingested_asset_ids: list[uuid.UUID],
    new_anomaly_events: list[AnomalyEvent] | None = None,
) -> int:
    """Run after ingestion+anomaly detection. Returns count of new alert events."""
    log.info("alert.evaluate_start", assets=len(ingested_asset_ids))

    rules = await _load_active_rules(db)
    if not rules:
        log.debug("alert.no_active_rules")
        return 0

    now = datetime.now(timezone.utc)
    created = 0

    for rule in rules:
        if _is_in_cooldown(rule, now):
            log.debug("alert.cooldown_skip", rule_id=str(rule.id), rule_name=rule.name)
            continue

        try:
            if rule.rule_type in ("price_above", "price_below"):
                created += await _evaluate_price_rule(db, rule, ingested_asset_ids, now)
            elif rule.rule_type in ("anomaly_detected", "anomaly_severity_min"):
                if new_anomaly_events:
                    created += await _evaluate_anomaly_rule(db, rule, new_anomaly_events, now)
        except Exception as e:
            log.error("alert.evaluate_error", rule_id=str(rule.id), error=str(e))

    log.info("alert.evaluate_done", rules_checked=len(rules), events_created=created)
    return created


async def _load_active_rules(db: AsyncSession) -> list[AlertRule]:
    result = await db.execute(
        select(AlertRule).where(AlertRule.is_active.is_(True))
    )
    return list(result.scalars().all())


def _is_in_cooldown(rule: AlertRule, now: datetime) -> bool:
    if not rule.last_triggered_at:
        return False
    return now < rule.last_triggered_at + timedelta(minutes=rule.cooldown_minutes)


async def _evaluate_price_rule(
    db: AsyncSession,
    rule: AlertRule,
    asset_ids: list[uuid.UUID],
    now: datetime,
) -> int:
    """Evaluate price_above / price_below rule. Returns events created."""
    threshold = rule.condition.get("threshold")
    if threshold is None:
        return 0

    # If rule targets specific asset, only check that one
    check_ids = [rule.asset_id] if rule.asset_id else asset_ids
    created = 0

    for aid in check_ids:
        if rule.asset_id and aid != rule.asset_id:
            continue

        price = await get_latest_price(db, aid)
        if not price:
            continue

        triggered = False
        if rule.rule_type == "price_above" and price.close > threshold:
            triggered = True
        elif rule.rule_type == "price_below" and price.close < threshold:
            triggered = True

        if triggered:
            direction = "above" if rule.rule_type == "price_above" else "below"
            event = AlertEvent(
                alert_rule_id=rule.id,
                asset_id=aid,
                triggered_at=now,
                message=f"Price ${price.close:,.2f} is {direction} threshold ${threshold:,.2f}",
                details={
                    "rule_type": rule.rule_type,
                    "threshold": threshold,
                    "actual_price": price.close,
                    "change_24h_pct": price.change_24h_pct,
                },
            )
            db.add(event)
            rule.last_triggered_at = now
            await db.flush()
            created += 1
            log.info(
                "alert.triggered",
                rule_id=str(rule.id),
                rule_type=rule.rule_type,
                asset_id=str(aid),
                price=price.close,
                threshold=threshold,
            )
            break  # One trigger per rule per evaluation cycle

    return created


async def _evaluate_anomaly_rule(
    db: AsyncSession,
    rule: AlertRule,
    anomaly_events: list[AnomalyEvent],
    now: datetime,
) -> int:
    """Evaluate anomaly_detected / anomaly_severity_min. Returns events created."""
    created = 0

    for anomaly in anomaly_events:
        # Filter by asset if rule specifies one
        if rule.asset_id and anomaly.asset_id != rule.asset_id:
            continue

        if rule.rule_type == "anomaly_detected":
            pass  # Any anomaly matches
        elif rule.rule_type == "anomaly_severity_min":
            min_sev = rule.condition.get("severity_min", "high")
            if SEVERITY_ORDER.get(anomaly.severity, 0) < SEVERITY_ORDER.get(min_sev, 2):
                continue
        else:
            continue

        event = AlertEvent(
            alert_rule_id=rule.id,
            anomaly_event_id=anomaly.id,
            asset_id=anomaly.asset_id,
            triggered_at=now,
            message=f"Anomaly {anomaly.anomaly_type} ({anomaly.severity}) detected",
            details={
                "rule_type": rule.rule_type,
                "anomaly_type": anomaly.anomaly_type,
                "severity": anomaly.severity,
                "score": float(anomaly.score),
            },
        )
        db.add(event)
        rule.last_triggered_at = now
        await db.flush()
        created += 1
        log.info(
            "alert.triggered",
            rule_id=str(rule.id),
            rule_type=rule.rule_type,
            anomaly_type=anomaly.anomaly_type,
            asset_id=str(anomaly.asset_id),
        )
        break  # One trigger per rule per evaluation cycle

    return created

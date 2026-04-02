"""Anomaly service — runs detectors, deduplicates, persists, resolves."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.anomalies.detectors.base import AnomalyCandidate, BaseDetector
from app.anomalies.detectors.price_spike import PriceSpikeDetector
from app.anomalies.detectors.volume_spike import VolumeSpikeDetector
from app.anomalies.detectors.rsi_extreme import RSIExtremeDetector
from app.anomalies.detectors.divergence import DivergenceDetector
from app.anomalies.detectors.squeeze import SqueezeDetector
from app.anomalies.models import AnomalyEvent
from app.indicators.calculators.rsi import calc_rsi
from app.indicators.service import get_closes_series
from app.logging_config import get_logger

log = get_logger(__name__)

# Deduplication: skip if same (asset, type) anomaly exists within this window
DEDUP_WINDOW_HOURS = 4

# All active detectors
DETECTORS: list[BaseDetector] = [
    PriceSpikeDetector(),
    VolumeSpikeDetector(),
    RSIExtremeDetector(),
    SqueezeDetector(),
    DivergenceDetector(),
]


async def run_anomaly_detection(
    db: AsyncSession,
    asset_id: uuid.UUID,
    asset_symbol: str,
    interval: str,
) -> list[AnomalyEvent]:
    """Run all detectors for one asset. Returns list of newly created AnomalyEvents."""
    log.debug("anomaly.scan_start", asset=asset_symbol, interval=interval)

    # Load data
    data = await get_closes_series(db, asset_id, interval, lookback=60)
    if data is None:
        log.debug("anomaly.no_data", asset=asset_symbol)
        return []

    closes, volumes = data

    if len(closes) < 15:
        log.debug("anomaly.insufficient_bars", asset=asset_symbol, bars=len(closes))
        return []

    # Pre-compute RSI for detectors that need it
    rsi_val = calc_rsi(closes, period=14)

    # Run all detectors
    now = datetime.now(timezone.utc)
    candidates: list[AnomalyCandidate] = []

    for detector in DETECTORS:
        try:
            candidate = detector.detect(closes=closes, volumes=volumes, rsi=rsi_val)
            if candidate is not None:
                candidates.append(candidate)
                log.info(
                    "anomaly.detected",
                    asset=asset_symbol,
                    type=candidate.anomaly_type,
                    severity=candidate.severity,
                    score=candidate.score,
                )
        except Exception as e:
            log.warning(
                "anomaly.detector_error",
                detector=detector.name,
                asset=asset_symbol,
                error=str(e),
            )

    # Deduplicate and persist
    created: list[AnomalyEvent] = []
    for candidate in candidates:
        if await _is_duplicate(db, asset_id, candidate.anomaly_type, now):
            log.debug(
                "anomaly.duplicate_skip",
                asset=asset_symbol,
                type=candidate.anomaly_type,
            )
            continue

        event = AnomalyEvent(
            asset_id=asset_id,
            detected_at=now,
            anomaly_type=candidate.anomaly_type,
            severity=candidate.severity,
            score=candidate.score,
            details=candidate.details,
            timeframe=interval,
            is_resolved=False,
        )
        db.add(event)
        created.append(event)
        log.info(
            "anomaly.persisted",
            asset=asset_symbol,
            type=candidate.anomaly_type,
            severity=candidate.severity,
        )

    # Resolve old anomalies whose conditions are no longer met
    resolved_count = await _resolve_stale_anomalies(db, asset_id, interval, candidates, now)
    if resolved_count > 0:
        log.info("anomaly.resolved", asset=asset_symbol, count=resolved_count)

    await db.flush()

    log.debug(
        "anomaly.scan_done",
        asset=asset_symbol,
        candidates=len(candidates),
        created=len(created),
        resolved=resolved_count,
    )
    return created


async def run_anomaly_detection_batch(
    db: AsyncSession,
    assets: list[tuple[uuid.UUID, str]],
    interval: str,
) -> int:
    """Run anomaly detection for multiple assets. Returns total new anomalies."""
    total = 0
    for asset_id, symbol in assets:
        try:
            created = await run_anomaly_detection(db, asset_id, symbol, interval)
            total += len(created)
        except Exception as e:
            log.error("anomaly.batch_asset_error", asset=symbol, error=str(e))
    return total


async def _is_duplicate(
    db: AsyncSession,
    asset_id: uuid.UUID,
    anomaly_type: str,
    now: datetime,
) -> bool:
    """Check if an active anomaly of the same type exists within the dedup window."""
    cutoff = now - timedelta(hours=DEDUP_WINDOW_HOURS)
    result = await db.execute(
        select(AnomalyEvent.id)
        .where(
            and_(
                AnomalyEvent.asset_id == asset_id,
                AnomalyEvent.anomaly_type == anomaly_type,
                AnomalyEvent.is_resolved.is_(False),
                AnomalyEvent.detected_at >= cutoff,
            )
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _resolve_stale_anomalies(
    db: AsyncSession,
    asset_id: uuid.UUID,
    interval: str,
    current_candidates: list[AnomalyCandidate],
    now: datetime,
) -> int:
    """Resolve unresolved anomalies whose type is no longer detected."""
    active_types = {c.anomaly_type for c in current_candidates}

    result = await db.execute(
        select(AnomalyEvent).where(
            and_(
                AnomalyEvent.asset_id == asset_id,
                AnomalyEvent.timeframe == interval,
                AnomalyEvent.is_resolved.is_(False),
            )
        )
    )
    unresolved = result.scalars().all()

    count = 0
    for event in unresolved:
        if event.anomaly_type not in active_types:
            event.is_resolved = True
            event.resolved_at = now
            count += 1

    return count

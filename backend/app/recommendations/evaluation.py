"""Recommendation evaluation — measures forward returns after 24h/72h."""

import time as _time
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, select, case, literal
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.assets.service import get_latest_price
from app.logging_config import get_logger
from app.recommendations.models import Recommendation

log = get_logger(__name__)


async def evaluate_recommendations(db: AsyncSession) -> dict:
    """Check all recommendations due for 24h/72h evaluation. Returns counts."""
    now = datetime.now(timezone.utc)
    t_start = _time.monotonic()
    evaluated_24h = 0
    evaluated_72h = 0

    # Find recs needing 24h evaluation: generated >= 24h ago, not yet evaluated
    cutoff_24h = now - timedelta(hours=24)
    recs_24h = await db.execute(
        select(Recommendation).where(
            and_(
                Recommendation.generated_at <= cutoff_24h,
                Recommendation.evaluated_at_24h.is_(None),
                Recommendation.entry_price_snapshot.isnot(None),
            )
        ).limit(100)
    )
    for rec in recs_24h.scalars().all():
        try:
            price_data = await get_latest_price(db, rec.asset_id)
            if not price_data:
                continue
            entry = float(rec.entry_price_snapshot)
            if entry <= 0:
                continue
            current = price_data.close
            ret_pct = round((current - entry) / entry * 100, 4)

            rec.price_after_24h = current
            rec.return_24h_pct = ret_pct
            rec.evaluated_at_24h = now
            evaluated_24h += 1

            log.info(
                "recommendation.evaluate_done",
                recommendation_id=str(rec.id),
                horizon="24h",
                entry_price=entry,
                eval_price=current,
                return_pct=ret_pct,
            )
        except Exception as e:
            log.error("recommendation.evaluate_error",
                      recommendation_id=str(rec.id), horizon="24h", error=str(e))

    # Find recs needing 72h evaluation
    cutoff_72h = now - timedelta(hours=72)
    recs_72h = await db.execute(
        select(Recommendation).where(
            and_(
                Recommendation.generated_at <= cutoff_72h,
                Recommendation.evaluated_at_72h.is_(None),
                Recommendation.entry_price_snapshot.isnot(None),
            )
        ).limit(100)
    )
    for rec in recs_72h.scalars().all():
        try:
            price_data = await get_latest_price(db, rec.asset_id)
            if not price_data:
                continue
            entry = float(rec.entry_price_snapshot)
            if entry <= 0:
                continue
            current = price_data.close
            ret_pct = round((current - entry) / entry * 100, 4)

            rec.price_after_72h = current
            rec.return_72h_pct = ret_pct
            rec.evaluated_at_72h = now
            evaluated_72h += 1

            log.info(
                "recommendation.evaluate_done",
                recommendation_id=str(rec.id),
                horizon="72h",
                entry_price=entry,
                eval_price=current,
                return_pct=ret_pct,
            )
        except Exception as e:
            log.error("recommendation.evaluate_error",
                      recommendation_id=str(rec.id), horizon="72h", error=str(e))

    if evaluated_24h or evaluated_72h:
        await db.commit()

    duration_ms = int((_time.monotonic() - t_start) * 1000)
    if evaluated_24h or evaluated_72h:
        log.info("recommendation.evaluation_batch_done",
                 evaluated_24h=evaluated_24h, evaluated_72h=evaluated_72h,
                 duration_ms=duration_ms)

    return {"evaluated_24h": evaluated_24h, "evaluated_72h": evaluated_72h}


async def get_performance_metrics(db: AsyncSession) -> dict:
    """Compute recommendation engine performance metrics."""
    # Total counts
    total_res = await db.execute(select(func.count(Recommendation.id)))
    total = total_res.scalar_one()

    active_res = await db.execute(
        select(func.count(Recommendation.id)).where(Recommendation.status == "active")
    )
    active = active_res.scalar_one()

    eval_24h_res = await db.execute(
        select(func.count(Recommendation.id)).where(Recommendation.evaluated_at_24h.isnot(None))
    )
    evaluated_24h = eval_24h_res.scalar_one()

    eval_72h_res = await db.execute(
        select(func.count(Recommendation.id)).where(Recommendation.evaluated_at_72h.isnot(None))
    )
    evaluated_72h = eval_72h_res.scalar_one()

    # Average returns
    avg_24h_res = await db.execute(
        select(func.avg(Recommendation.return_24h_pct)).where(Recommendation.return_24h_pct.isnot(None))
    )
    avg_return_24h = avg_24h_res.scalar_one()

    avg_72h_res = await db.execute(
        select(func.avg(Recommendation.return_72h_pct)).where(Recommendation.return_72h_pct.isnot(None))
    )
    avg_return_72h = avg_72h_res.scalar_one()

    # Accuracy by recommendation_type (24h)
    by_type = await _accuracy_by_type(db)

    # Accuracy by asset_class
    by_class = await _accuracy_by_class(db)

    # Accuracy by score bucket
    by_bucket = await _accuracy_by_score_bucket(db)

    # By scoring version
    by_version = await _accuracy_by_version(db)

    return {
        "summary": {
            "total_recommendations": total,
            "active_recommendations": active,
            "evaluated_24h": evaluated_24h,
            "evaluated_72h": evaluated_72h,
            "avg_return_24h_pct": round(float(avg_return_24h), 4) if avg_return_24h else None,
            "avg_return_72h_pct": round(float(avg_return_72h), 4) if avg_return_72h else None,
        },
        "by_version": by_version,
        "by_type": by_type,
        "by_asset_class": by_class,
        "by_score_bucket": by_bucket,
    }


async def _accuracy_by_type(db: AsyncSession) -> list[dict]:
    """Accuracy grouped by recommendation_type."""
    result = await db.execute(
        select(
            Recommendation.recommendation_type,
            func.count().label("total"),
            func.count(Recommendation.return_24h_pct).label("evaluated"),
            func.avg(Recommendation.return_24h_pct).label("avg_return_24h"),
            func.avg(Recommendation.return_72h_pct).label("avg_return_72h"),
            func.sum(case(
                (Recommendation.return_24h_pct > 0, 1), else_=0
            )).label("positive_24h"),
        )
        .group_by(Recommendation.recommendation_type)
        .order_by(Recommendation.recommendation_type)
    )
    return [
        {
            "type": row.recommendation_type,
            "total": row.total,
            "evaluated": row.evaluated,
            "avg_return_24h_pct": round(float(row.avg_return_24h), 4) if row.avg_return_24h else None,
            "avg_return_72h_pct": round(float(row.avg_return_72h), 4) if row.avg_return_72h else None,
            "accuracy_24h_pct": round(int(row.positive_24h) / row.evaluated * 100, 1) if row.evaluated else None,
        }
        for row in result.all()
    ]


async def _accuracy_by_class(db: AsyncSession) -> list[dict]:
    """Accuracy grouped by asset_class."""
    result = await db.execute(
        select(
            Asset.asset_class,
            func.count().label("total"),
            func.count(Recommendation.return_24h_pct).label("evaluated"),
            func.avg(Recommendation.return_24h_pct).label("avg_return_24h"),
            func.avg(Recommendation.return_72h_pct).label("avg_return_72h"),
            func.sum(case(
                (Recommendation.return_24h_pct > 0, 1), else_=0
            )).label("positive_24h"),
        )
        .join(Asset, Recommendation.asset_id == Asset.id)
        .group_by(Asset.asset_class)
        .order_by(Asset.asset_class)
    )
    return [
        {
            "asset_class": row.asset_class,
            "total": row.total,
            "evaluated": row.evaluated,
            "avg_return_24h_pct": round(float(row.avg_return_24h), 4) if row.avg_return_24h else None,
            "avg_return_72h_pct": round(float(row.avg_return_72h), 4) if row.avg_return_72h else None,
            "accuracy_24h_pct": round(int(row.positive_24h) / row.evaluated * 100, 1) if row.evaluated else None,
        }
        for row in result.all()
    ]


async def _accuracy_by_score_bucket(db: AsyncSession) -> list[dict]:
    """Accuracy grouped by score bucket."""
    bucket_expr = case(
        (Recommendation.score >= 70, "70-100"),
        (Recommendation.score >= 55, "55-69"),
        (Recommendation.score >= 40, "40-54"),
        else_="0-39",
    )
    result = await db.execute(
        select(
            bucket_expr.label("bucket"),
            func.count().label("total"),
            func.count(Recommendation.return_24h_pct).label("evaluated"),
            func.avg(Recommendation.return_24h_pct).label("avg_return_24h"),
            func.avg(Recommendation.return_72h_pct).label("avg_return_72h"),
            func.sum(case(
                (Recommendation.return_24h_pct > 0, 1), else_=0
            )).label("positive_24h"),
        )
        .group_by(bucket_expr)
        .order_by(bucket_expr.desc())
    )
    return [
        {
            "bucket": row.bucket,
            "total": row.total,
            "evaluated": row.evaluated,
            "avg_return_24h_pct": round(float(row.avg_return_24h), 4) if row.avg_return_24h else None,
            "avg_return_72h_pct": round(float(row.avg_return_72h), 4) if row.avg_return_72h else None,
            "accuracy_24h_pct": round(int(row.positive_24h) / row.evaluated * 100, 1) if row.evaluated else None,
        }
        for row in result.all()
    ]


async def _accuracy_by_version(db: AsyncSession) -> list[dict]:
    """Accuracy grouped by scoring_version — for before/after calibration comparison."""
    result = await db.execute(
        select(
            func.coalesce(Recommendation.scoring_version, "v1").label("version"),
            func.count().label("total"),
            func.count(Recommendation.return_24h_pct).label("evaluated"),
            func.avg(Recommendation.return_24h_pct).label("avg_return_24h"),
            func.avg(Recommendation.return_72h_pct).label("avg_return_72h"),
            func.sum(case(
                (Recommendation.return_24h_pct > 0, 1), else_=0
            )).label("positive_24h"),
        )
        .group_by(func.coalesce(Recommendation.scoring_version, "v1"))
        .order_by(func.coalesce(Recommendation.scoring_version, "v1"))
    )
    return [
        {
            "version": row.version,
            "total": row.total,
            "evaluated": row.evaluated,
            "avg_return_24h_pct": round(float(row.avg_return_24h), 4) if row.avg_return_24h else None,
            "avg_return_72h_pct": round(float(row.avg_return_72h), 4) if row.avg_return_72h else None,
            "accuracy_24h_pct": round(int(row.positive_24h) / row.evaluated * 100, 1) if row.evaluated else None,
        }
        for row in result.all()
    ]

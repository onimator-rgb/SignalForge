"""Evaluation status — quick operator check for recommendation evaluation progress.

Usage:
    cd backend && uv run python -m scripts.evaluation_status
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import text, func, select, and_
from app.database import async_session
from app.assets.models import Asset
from app.recommendations.models import Recommendation
from app.portfolio.models import PortfolioPosition
from app.anomalies.models import AnomalyEvent  # noqa


async def main():
    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)
    cutoff_72h = now - timedelta(hours=72)

    print(f"\n=== Evaluation Status ({now.strftime('%Y-%m-%d %H:%M UTC')}) ===\n")

    async with async_session() as db:
        # Totals
        total = (await db.execute(select(func.count(Recommendation.id)))).scalar_one()
        by_status = dict((await db.execute(
            select(Recommendation.status, func.count()).group_by(Recommendation.status)
        )).all())
        print(f"Recommendations: {total} total")
        for s, c in sorted(by_status.items()):
            print(f"  {s}: {c}")

        # 24h evaluation
        eligible_24h = (await db.execute(
            select(func.count()).where(
                Recommendation.generated_at <= cutoff_24h,
                Recommendation.entry_price_snapshot.isnot(None),
            )
        )).scalar_one()
        evaluated_24h = (await db.execute(
            select(func.count()).where(Recommendation.evaluated_at_24h.isnot(None))
        )).scalar_one()
        pending_24h = eligible_24h - evaluated_24h

        print(f"\n24h Evaluation:")
        print(f"  Eligible: {eligible_24h}  Evaluated: {evaluated_24h}  Pending: {pending_24h}")

        if evaluated_24h > 0:
            avg_ret = (await db.execute(
                select(func.round(func.avg(Recommendation.return_24h_pct), 4))
                .where(Recommendation.return_24h_pct.isnot(None))
            )).scalar_one()
            print(f"  Avg return 24h: {avg_ret}%")

        # 72h evaluation
        eligible_72h = (await db.execute(
            select(func.count()).where(
                Recommendation.generated_at <= cutoff_72h,
                Recommendation.entry_price_snapshot.isnot(None),
            )
        )).scalar_one()
        evaluated_72h = (await db.execute(
            select(func.count()).where(Recommendation.evaluated_at_72h.isnot(None))
        )).scalar_one()
        print(f"\n72h Evaluation:")
        print(f"  Eligible: {eligible_72h}  Evaluated: {evaluated_72h}  Pending: {eligible_72h - evaluated_72h}")

        # By version
        ver_label = func.coalesce(Recommendation.scoring_version, "v1").label("ver")
        ver_res = await db.execute(
            select(
                ver_label,
                func.count(),
                func.count(Recommendation.return_24h_pct),
                func.round(func.avg(Recommendation.return_24h_pct), 4),
            ).group_by(ver_label)
        )
        print(f"\nBy scoring version:")
        for ver, total, evaluated, avg_ret in ver_res.all():
            print(f"  {ver}: {total} total, {evaluated} evaluated, avg_ret_24h={avg_ret}")

        # By asset class
        class_res = await db.execute(
            select(
                Asset.asset_class,
                func.count(),
                func.count(Recommendation.return_24h_pct),
                func.round(func.avg(Recommendation.return_24h_pct), 4),
            )
            .select_from(Recommendation)
            .join(Asset, Recommendation.asset_id == Asset.id)
            .group_by(Asset.asset_class)
        )
        print(f"\nBy asset class:")
        for ac, total, evaluated, avg_ret in class_res.all():
            print(f"  {ac}: {total} total, {evaluated} evaluated, avg_ret_24h={avg_ret}")

        # Age info
        oldest = (await db.execute(select(func.min(Recommendation.generated_at)))).scalar_one()
        newest = (await db.execute(select(func.max(Recommendation.generated_at)))).scalar_one()
        if oldest:
            age_h = round((now - oldest).total_seconds() / 3600, 1)
            print(f"\nAge: oldest={age_h}h ago ({oldest.strftime('%m-%d %H:%M')})")
            print(f"     newest={round((now - newest).total_seconds() / 3600, 1)}h ago ({newest.strftime('%m-%d %H:%M')})")

        # Portfolio quick summary
        open_p = (await db.execute(select(func.count()).where(PortfolioPosition.status == "open"))).scalar_one()
        closed_p = (await db.execute(select(func.count()).where(PortfolioPosition.status == "closed"))).scalar_one()
        print(f"\nPortfolio: {open_p} open, {closed_p} closed")

        # Scheduler recent activity
        from app.ingestion.models import IngestionJob
        last_job = (await db.execute(
            select(IngestionJob.started_at, IngestionJob.provider)
            .order_by(IngestionJob.started_at.desc()).limit(1)
        )).one_or_none()
        if last_job:
            age = round((now - last_job.started_at).total_seconds() / 60, 1)
            print(f"\nLast ingestion: {last_job.provider} {age} min ago")

    print(f"\n{'=' * 50}\n")


if __name__ == "__main__":
    asyncio.run(main())

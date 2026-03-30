"""Runtime Doctor — single comprehensive diagnostic check.

Usage:
    cd backend && uv run python -m scripts.runtime_doctor
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import text, func, select
from app.database import async_session
from app.assets.models import Asset
from app.recommendations.models import Recommendation
from app.portfolio.models import PortfolioPosition
from app.anomalies.models import AnomalyEvent  # noqa


async def main():
    now = datetime.now(timezone.utc)
    print(f"\n{'='*60}")
    print(f"  Runtime Doctor — {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}\n")

    issues = []
    warnings = []

    async with async_session() as db:
        # 1. Heartbeats
        r = await db.execute(text("SELECT component, status, last_seen_at FROM runtime_heartbeats"))
        rows = r.fetchall()
        print("Components:")
        if not rows:
            print("  (no heartbeats recorded — backend may not have started)")
            issues.append("No heartbeats")
        for row in rows:
            age = round((now - row.last_seen_at).total_seconds() / 60, 1)
            status_icon = "OK" if age < 10 else ("WARN" if age < 30 else "DOWN")
            if status_icon == "DOWN":
                issues.append(f"{row.component} down ({age:.0f}m ago)")
            elif status_icon == "WARN":
                warnings.append(f"{row.component} stale ({age:.0f}m ago)")
            print(f"  {row.component:>20s}: {status_icon:>4s}  ({age:.0f}m ago)")

        # 2. Ingestion
        r = await db.execute(text(
            "SELECT provider, max(started_at) as last_at, count(*) as total "
            "FROM ingestion_jobs GROUP BY provider"
        ))
        print("\nIngestion:")
        for row in r.fetchall():
            age = round((now - row.last_at).total_seconds() / 60, 1)
            print(f"  {row.provider:>15s}: {row.total} jobs, last {age:.0f}m ago")
            if age > 60:
                warnings.append(f"Ingestion {row.provider} stale ({age:.0f}m)")

        # 3. Recommendations
        total = (await db.execute(select(func.count(Recommendation.id)))).scalar_one()
        active = (await db.execute(
            select(func.count()).where(Recommendation.status == "active")
        )).scalar_one()
        newest = (await db.execute(select(func.max(Recommendation.generated_at)))).scalar_one()
        rec_age = round((now - newest).total_seconds() / 60, 1) if newest else 9999
        print(f"\nRecommendations: {total} total, {active} active, newest {rec_age:.0f}m ago")
        if rec_age > 30:
            warnings.append(f"Recommendations stale ({rec_age:.0f}m)")

        # 4. Evaluation
        cutoff_24h = now - timedelta(hours=24)
        eligible = (await db.execute(
            select(func.count()).where(
                Recommendation.generated_at <= cutoff_24h,
                Recommendation.entry_price_snapshot.isnot(None),
            )
        )).scalar_one()
        evaluated = (await db.execute(
            select(func.count()).where(Recommendation.evaluated_at_24h.isnot(None))
        )).scalar_one()
        pending = eligible - evaluated
        print(f"\nEvaluation 24h: eligible={eligible} evaluated={evaluated} pending={pending}")
        if pending > 0 and evaluated == 0:
            warnings.append(f"Evaluation: {pending} pending, 0 evaluated")

        # 5. Portfolio
        open_p = (await db.execute(select(func.count()).where(PortfolioPosition.status == "open"))).scalar_one()
        closed_p = (await db.execute(select(func.count()).where(PortfolioPosition.status == "closed"))).scalar_one()
        print(f"\nPortfolio: {open_p} open, {closed_p} closed")

        # 6. Live cache
        try:
            from app.live.cache import get_all_prices
            cache = get_all_prices()
            print(f"\nLive cache: {len(cache)} entries")
            if len(cache) == 0:
                warnings.append("Live cache empty")
        except Exception:
            print("\nLive cache: unavailable")

    # Verdict
    print(f"\n{'='*60}")
    if issues:
        print(f"  VERDICT: FAIL")
        for i in issues:
            print(f"    [ISSUE] {i}")
    elif warnings:
        print(f"  VERDICT: WARN")
    else:
        print(f"  VERDICT: OK")

    for w in warnings:
        print(f"    [WARN] {w}")

    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())

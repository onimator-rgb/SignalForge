"""Score calibration review — analyzes recommendation performance data."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import text
from app.database import async_session
from app.anomalies.models import AnomalyEvent  # noqa


async def main():
    print("\n=== Score Calibration Review ===\n")

    async with async_session() as db:
        # 1. All recs breakdown
        r = await db.execute(text(
            "SELECT coalesce(scoring_version, 'v1') as ver, recommendation_type, status, "
            "count(*) as cnt, round(avg(score)::numeric, 2) as avg_s "
            "FROM recommendations "
            "GROUP BY 1, 2, 3 ORDER BY 1, 2, 3"
        ))
        print("All recommendations:")
        for row in r.fetchall():
            print(f"  {row.ver:>3s} {row.recommendation_type:>14s} {row.status:>10s}  n={row.cnt:3d}  avg={row.avg_s}")

        # 2. Evaluation status
        r = await db.execute(text(
            "SELECT count(*) as total, "
            "count(evaluated_at_24h) as eval_24h, "
            "count(evaluated_at_72h) as eval_72h, "
            "round(avg(return_24h_pct)::numeric, 4) as avg_ret_24h, "
            "round(avg(return_72h_pct)::numeric, 4) as avg_ret_72h "
            "FROM recommendations"
        ))
        row = r.fetchone()
        print(f"\nEvaluation: total={row.total} eval_24h={row.eval_24h} eval_72h={row.eval_72h}")
        print(f"  avg_return_24h={row.avg_ret_24h}  avg_return_72h={row.avg_ret_72h}")

        # 3. By type
        r = await db.execute(text(
            "SELECT recommendation_type, count(*) as total, "
            "count(return_24h_pct) as evaluated, "
            "round(avg(return_24h_pct)::numeric, 4) as avg_ret_24h, "
            "sum(case when return_24h_pct > 0 then 1 else 0 end) as positive_24h "
            "FROM recommendations GROUP BY 1 ORDER BY 1"
        ))
        print("\nBy type:")
        for row in r.fetchall():
            acc = f"{round(int(row.positive_24h) / row.evaluated * 100, 1)}%" if row.evaluated else "--"
            print(f"  {row.recommendation_type:>14s}  total={row.total:3d}  eval={row.evaluated:3d}  avg_ret={row.avg_ret_24h}  acc={acc}")

        # 4. By asset class
        r = await db.execute(text(
            "SELECT a.asset_class, count(*) as total, "
            "count(r.return_24h_pct) as evaluated, "
            "round(avg(r.return_24h_pct)::numeric, 4) as avg_ret, "
            "round(avg(r.score)::numeric, 2) as avg_score "
            "FROM recommendations r JOIN assets a ON r.asset_id = a.id "
            "GROUP BY 1"
        ))
        print("\nBy asset class:")
        for row in r.fetchall():
            print(f"  {row.asset_class:>8s}  total={row.total:3d}  eval={row.evaluated:3d}  avg_ret={row.avg_ret}  avg_score={row.avg_score}")

        # 5. By version
        r = await db.execute(text(
            "SELECT coalesce(scoring_version, 'v1') as ver, "
            "count(*) as total, "
            "count(return_24h_pct) as evaluated, "
            "round(avg(return_24h_pct)::numeric, 4) as avg_ret, "
            "round(avg(score)::numeric, 2) as avg_score "
            "FROM recommendations GROUP BY 1 ORDER BY 1"
        ))
        print("\nBy scoring version:")
        for row in r.fetchall():
            print(f"  {row.ver}  total={row.total:3d}  eval={row.evaluated:3d}  avg_ret={row.avg_ret}  avg_score={row.avg_score}")

        # 6. Score buckets
        r = await db.execute(text(
            "SELECT CASE "
            "WHEN score >= 70 THEN '70-100' "
            "WHEN score >= 63 THEN '63-69' "
            "WHEN score >= 55 THEN '55-62' "
            "WHEN score >= 45 THEN '45-54' "
            "ELSE '0-44' END as bucket, "
            "count(*) as cnt, count(return_24h_pct) as evaluated, "
            "round(avg(return_24h_pct)::numeric, 4) as avg_ret "
            "FROM recommendations GROUP BY 1 ORDER BY 1"
        ))
        print("\nScore buckets:")
        for row in r.fetchall():
            bar = "#" * row.cnt
            print(f"  {row.bucket:>8s}  n={row.cnt:3d}  eval={row.evaluated:3d}  avg_ret={row.avg_ret}  {bar}")

        # 7. Portfolio
        r = await db.execute(text(
            "SELECT status, count(*) as cnt, "
            "round(avg(realized_pnl_pct)::numeric, 4) as avg_pnl, "
            "round(sum(realized_pnl_usd)::numeric, 2) as total_pnl "
            "FROM portfolio_positions GROUP BY 1"
        ))
        print("\nPortfolio:")
        for row in r.fetchall():
            print(f"  {row.status}: n={row.cnt} avg_pnl={row.avg_pnl}% total=${row.total_pnl}")

        # 8. Active distribution
        r = await db.execute(text(
            "SELECT a.asset_class, r.recommendation_type, count(*) as cnt, "
            "round(avg(r.score)::numeric, 1) as avg "
            "FROM recommendations r JOIN assets a ON r.asset_id = a.id "
            "WHERE r.status = 'active' "
            "GROUP BY 1, 2 ORDER BY 1, 2"
        ))
        print("\nActive signal distribution:")
        for row in r.fetchall():
            print(f"  {row.asset_class:>8s} {row.recommendation_type:>14s}  n={row.cnt:3d}  avg={row.avg}")

    print("\n" + "=" * 50)


if __name__ == "__main__":
    asyncio.run(main())

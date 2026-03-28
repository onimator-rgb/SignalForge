"""Quick sanity check — DB-level summary of system state.

No running backend needed — connects directly to PostgreSQL.

Usage:
    cd backend && uv run python -m scripts.sanity_check
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import text
from app.database import async_session
from app.anomalies.models import AnomalyEvent  # noqa: F401


async def main() -> None:
    print("\n=== MarketPulse AI — Sanity Check ===\n")

    async with async_session() as db:
        # Assets
        r = await db.execute(text(
            "SELECT asset_class, count(*) as cnt, "
            "sum(CASE WHEN is_active THEN 1 ELSE 0 END) as active "
            "FROM assets GROUP BY asset_class ORDER BY asset_class"
        ))
        print("Assets:")
        for row in r.fetchall():
            print(f"  {row.asset_class:>6s}: {row.cnt} total, {row.active} active")

        # Price bars
        r = await db.execute(text(
            "SELECT a.asset_class, pb.interval, count(*) as bars, "
            "count(DISTINCT pb.asset_id) as assets_with_data, "
            "min(pb.time) as oldest, max(pb.time) as newest "
            "FROM price_bars pb "
            "JOIN assets a ON pb.asset_id = a.id "
            "GROUP BY a.asset_class, pb.interval "
            "ORDER BY a.asset_class, pb.interval"
        ))
        print("\nPrice bars:")
        for row in r.fetchall():
            newest = row.newest.strftime("%Y-%m-%d %H:%M") if row.newest else "?"
            print(f"  {row.asset_class:>6s} {row.interval}: {row.bars:>6d} bars "
                  f"({row.assets_with_data} assets) newest={newest}")

        # Anomalies
        r = await db.execute(text(
            "SELECT a.asset_class, "
            "count(*) as total, "
            "sum(CASE WHEN NOT ae.is_resolved THEN 1 ELSE 0 END) as unresolved "
            "FROM anomaly_events ae "
            "JOIN assets a ON ae.asset_id = a.id "
            "GROUP BY a.asset_class ORDER BY a.asset_class"
        ))
        rows = r.fetchall()
        print("\nAnomalies:")
        if rows:
            for row in rows:
                print(f"  {row.asset_class:>6s}: {row.total} total, {row.unresolved} unresolved")
        else:
            print("  (none)")

        # Alerts
        r = await db.execute(text(
            "SELECT count(*) as rules, "
            "sum(CASE WHEN is_active THEN 1 ELSE 0 END) as active "
            "FROM alert_rules"
        ))
        row = r.fetchone()
        r2 = await db.execute(text(
            "SELECT count(*) as total, "
            "sum(CASE WHEN NOT is_read THEN 1 ELSE 0 END) as unread "
            "FROM alert_events"
        ))
        row2 = r2.fetchone()
        print(f"\nAlerts:")
        print(f"  Rules: {row.rules} total, {row.active} active")
        print(f"  Events: {row2.total} total, {row2.unread} unread")

        # Reports
        r = await db.execute(text(
            "SELECT status, count(*) as cnt "
            "FROM analysis_reports GROUP BY status ORDER BY status"
        ))
        rows = r.fetchall()
        print(f"\nReports:")
        if rows:
            for row in rows:
                print(f"  {row.status:>12s}: {row.cnt}")
        else:
            print("  (none)")

        # Recommendations
        r = await db.execute(text(
            "SELECT scoring_version, recommendation_type, count(*) as cnt, "
            "round(avg(score)::numeric, 1) as avg_s "
            "FROM recommendations WHERE status = 'active' "
            "GROUP BY scoring_version, recommendation_type "
            "ORDER BY scoring_version, recommendation_type"
        ))
        rows = r.fetchall()
        print(f"\nActive recommendations:")
        for row in rows:
            print(f"  {row.scoring_version or 'v1':>3s} {row.recommendation_type:>14s}: {row.cnt:3d} (avg={row.avg_s})")

        # Evaluation
        r = await db.execute(text(
            "SELECT count(*) as total, "
            "count(evaluated_at_24h) as eval_24h, "
            "count(evaluated_at_72h) as eval_72h, "
            "round(avg(return_24h_pct)::numeric, 3) as avg_ret_24h "
            "FROM recommendations"
        ))
        row = r.fetchone()
        print(f"\nEvaluation: total={row.total} eval_24h={row.eval_24h} eval_72h={row.eval_72h} avg_ret_24h={row.avg_ret_24h}")

        # Portfolio
        r = await db.execute(text(
            "SELECT status, count(*) as cnt FROM portfolio_positions GROUP BY status ORDER BY status"
        ))
        rows = r.fetchall()
        print(f"\nPortfolio positions:")
        for row in rows:
            print(f"  {row.status}: {row.cnt}")
        r = await db.execute(text(
            "SELECT round(current_cash::numeric, 2) as cash, round(initial_capital::numeric, 2) as cap "
            "FROM portfolios WHERE is_active LIMIT 1"
        ))
        row = r.fetchone()
        if row:
            print(f"  cash=${row.cash} / initial=${row.cap}")

        # Live prices cache state
        try:
            from app.live.cache import get_all_prices
            cache = get_all_prices()
            print(f"\nLive price cache: {len(cache)} entries")
        except Exception:
            print(f"\nLive price cache: unavailable (backend not running?)")

        # Ingestion jobs (last 5)
        r = await db.execute(text(
            "SELECT provider, status, assets_success, assets_failed, "
            "records_inserted, duration_ms, started_at "
            "FROM ingestion_jobs ORDER BY started_at DESC LIMIT 5"
        ))
        rows = r.fetchall()
        print(f"\nRecent ingestion jobs:")
        for row in rows:
            ts = row.started_at.strftime("%m-%d %H:%M") if row.started_at else "?"
            print(f"  {ts} [{row.provider:>13s}] {row.status:>9s} "
                  f"ok={row.assets_success} fail={row.assets_failed} "
                  f"inserted={row.records_inserted} {row.duration_ms}ms")

        # Sync state errors
        r = await db.execute(text(
            "SELECT a.symbol, ps.provider, ps.interval, ps.consecutive_errors, ps.last_error "
            "FROM provider_sync_states ps "
            "JOIN assets a ON ps.asset_id = a.id "
            "WHERE ps.consecutive_errors > 0 "
            "ORDER BY ps.consecutive_errors DESC LIMIT 10"
        ))
        rows = r.fetchall()
        if rows:
            print(f"\nSync errors:")
            for row in rows:
                print(f"  {row.symbol:>6s} [{row.provider} {row.interval}] "
                      f"errors={row.consecutive_errors}: {(row.last_error or '')[:60]}")
        else:
            print(f"\nSync errors: none")

    print(f"\n{'=' * 40}\n")


if __name__ == "__main__":
    asyncio.run(main())

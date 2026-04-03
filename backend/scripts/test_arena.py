"""Quick test script — initialize arena, fetch news, run one evaluation.

Usage:
    cd marketpulse-ai/backend
    ../.venv/Scripts/python.exe scripts/test_arena.py
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import engine, async_session
from app.ai_traders.arena import initialize_arena, run_evaluation_round, get_leaderboard, take_daily_snapshots
from app.news.aggregator import NewsAggregator


async def main():
    print("=" * 60)
    print("  AI TRADER ARENA — First Test Run")
    print("=" * 60)

    # Step 1: Initialize traders
    print("\n[1/4] Initializing AI traders...")
    async with async_session() as db:
        results = await initialize_arena(db)
        for r in results:
            status = "NEW" if r["status"] == "created" else "EXISTS"
            print(f"  {status}: {r['slug']}")

    # Step 2: Fetch news
    print("\n[2/4] Fetching verified news from 3 sources...")
    aggregator = NewsAggregator()
    news = await aggregator.get_verified_news(limit=10)
    print(f"  Fetched {len(news)} verified articles")
    for n in news[:3]:
        verified = " [VERIFIED]" if n.raw_data.get("cross_source_count", 1) >= 2 else ""
        print(f"  - [{n.sentiment or 'neutral'}] {n.title[:70]}...{verified}")

    # Save news to DB
    async with async_session() as db:
        saved = await aggregator.save_to_db(db, news)
        await db.commit()
        print(f"  Saved {saved} new articles to DB")

    # Step 3: Run evaluation round
    print("\n[3/4] Running evaluation round (all traders x all assets)...")
    print("  This may take 1-3 minutes (LLM calls)...")
    async with async_session() as db:
        summary = await run_evaluation_round(db)
        await db.commit()

    print(f"\n  Results:")
    print(f"  Traders evaluated: {summary.get('traders_evaluated', 0)}")
    print(f"  Assets evaluated:  {summary.get('assets_evaluated', 0)}")
    print(f"  Pre-filtered:      {summary.get('pre_filtered', 0)} (saved LLM calls)")
    print(f"  LLM calls made:    {summary.get('llm_calls', 0)}")
    print(f"  Decisions made:    {summary.get('decisions_made', 0)}")
    print(f"  Trades executed:   {summary.get('trades_executed', 0)}")
    print(f"  Hard exits:        {summary.get('hard_exits', 0)}")

    # Show some decisions
    decisions = summary.get("decisions", [])
    executed = [d for d in decisions if d.get("executed")]
    if executed:
        print(f"\n  Executed trades:")
        for d in executed[:10]:
            print(f"    {d['trader']:25s} {d['action']:4s} {d['asset']:6s} (conf: {d['confidence']:.2f})")

    # Step 4: Leaderboard
    print("\n[4/4] Leaderboard:")
    async with async_session() as db:
        lb = await get_leaderboard(db)

    print(f"\n  {'#':>2} {'Trader':25s} {'Value':>10s} {'Return':>8s} {'Trades':>7s} {'W/L':>7s}")
    print(f"  {'-'*65}")
    for entry in lb:
        wl = f"{entry['wins']}/{entry['losses']}"
        print(f"  {entry['rank']:2d} {entry['name']:25s} ${entry['portfolio_value_usd']:>8.2f} {entry['total_return_pct']:>+7.2f}% {entry['total_trades']:>6d}  {wl:>6s}")

    # Take daily snapshot
    async with async_session() as db:
        snapshots = await take_daily_snapshots(db)
        await db.commit()
        print(f"\n  Daily snapshots saved: {len(snapshots)}")

    print("\n" + "=" * 60)
    print("  Arena test complete!")
    print("=" * 60)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

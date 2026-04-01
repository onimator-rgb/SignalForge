"""Run MarketPulse AI Orchestrator → Coder → Validator agent session.

Usage (from repo root):
    # Full 120-minute session
    python scripts/run_agents_session.py

    # Quick 10-minute test
    python scripts/run_agents_session.py --max-minutes 10

    # Single task only (for testing)
    python scripts/run_agents_session.py --single-task

    # Dry run (no commits)
    python scripts/run_agents_session.py --dry-run

    # Only Tier 1 features
    python scripts/run_agents_session.py --tier 1
"""

from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORT_DIR = REPO_ROOT / "reports"

# Add orchestrator to path
sys.path.insert(0, str(REPO_ROOT / "marketpulse-orchestrator"))


def main():
    parser = argparse.ArgumentParser(description="MarketPulse AI Agent Session")
    parser.add_argument("--max-minutes", type=int, default=120,
                        help="Maximum session duration in minutes (default: 120)")
    parser.add_argument("--dry-run", action="store_true",
                        help="No commits — coder runs in dry-run mode")
    parser.add_argument("--single-task", action="store_true",
                        help="Run one task then stop (for testing)")
    parser.add_argument("--tier", action="append", dest="tiers",
                        help="Which tiers to implement (default: all). Can repeat: --tier 1 --tier 2")
    args = parser.parse_args()

    tiers = args.tiers or ["1", "2", "3", "4", "5"]

    # Verify claude CLI
    print("=" * 60, flush=True)
    print(" MarketPulse AI — Orchestrator Agent Session", flush=True)
    print("=" * 60, flush=True)

    try:
        r = subprocess.run("claude --version", shell=True, capture_output=True, text=True, timeout=10)
        print(f" Claude CLI: {r.stdout.strip()}", flush=True)
    except Exception:
        print(" WARNING: claude CLI not found! Agents need it for --use-max mode.", flush=True)

    print(f" Max minutes: {args.max_minutes}", flush=True)
    print(f" Tiers: {tiers}", flush=True)
    print(f" Dry run: {args.dry_run}", flush=True)
    print(f" Single task: {args.single_task}", flush=True)
    print("=" * 60, flush=True)

    # Import and run orchestrator
    from orchestrator import Orchestrator

    orchestrator = Orchestrator(
        repo_path=str(REPO_ROOT),
        max_minutes=args.max_minutes,
        max_retries=2,
        dry_run=args.dry_run,
        tiers=tiers,
    )

    report = orchestrator.run_loop(single_task=args.single_task)

    # Save report
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    md_path = REPORT_DIR / f"orchestrator_report_{ts}.md"
    md_path.write_text(report.get("markdown", "No report generated"), encoding="utf-8")

    json_path = REPORT_DIR / f"orchestrator_report_{ts}.json"
    report_data = {k: v for k, v in report.items() if k != "markdown"}
    json_path.write_text(json.dumps(report_data, indent=2, default=str, ensure_ascii=False), encoding="utf-8")

    # Print summary
    print(f"\n{'='*60}", flush=True)
    print(f" Session complete!", flush=True)
    print(f" Completed: {report.get('completed_count', 0)}", flush=True)
    print(f" Failed: {report.get('failed_count', 0)}", flush=True)
    print(f" Files changed: {len(report.get('files_changed', []))}", flush=True)
    print(f" Duration: {report.get('elapsed_minutes', 0):.1f} min", flush=True)
    print(f" Cost: $0.00 (Claude MAX subscription)", flush=True)
    print(f"", flush=True)
    print(f" Report: {md_path}", flush=True)
    print(f" Data: {json_path}", flush=True)
    print(f"{'='*60}", flush=True)


if __name__ == "__main__":
    main()

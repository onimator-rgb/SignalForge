"""Run MarketPulse AI backend for 24h with periodic snapshots and comprehensive audit report.

Usage (from repo root — run in a separate terminal from the backend):
    # Start backend first:
    cd backend && .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000

    # Then in another terminal:
    .\\backend\\.venv\\Scripts\\python.exe scripts\\run_24h_audit.py

    # Or shorter duration for testing:
    .\\backend\\.venv\\Scripts\\python.exe scripts\\run_24h_audit.py --hours 1

The script assumes the backend is ALREADY running. It:
  1. Takes snapshots every 30 minutes via API endpoints
  2. After the duration, generates a comprehensive audit report
  3. Analyzes: indicator accuracy, recommendation performance, portfolio P&L,
     anomaly detection quality, system health, and optimization suggestions
"""

from __future__ import annotations

import datetime
import json
import sys
import time
from pathlib import Path

import httpx

BASE_URL = "http://localhost:8000"
REPORT_DIR = Path(__file__).resolve().parent.parent / "reports"

SNAPSHOT_INTERVAL_MIN = 30


def api_get(path: str, timeout: float = 15.0) -> dict | None:
    try:
        r = httpx.get(f"{BASE_URL}{path}", timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"_error": str(e)}


def check_backend() -> bool:
    try:
        r = httpx.get(f"{BASE_URL}/api/v1/health", timeout=5)
        return r.status_code == 200 and r.json().get("status") == "ok"
    except Exception:
        return False


def take_snapshot(label: str) -> dict:
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    print(f"\n[{label}] Snapshot at {ts[:19]} ...", flush=True)

    snap = {"label": label, "timestamp": ts}
    snap["health"] = api_get("/api/v1/health")
    snap["runtime"] = api_get("/api/v1/runtime-status")
    snap["summary"] = api_get("/api/v1/runtime-summary")
    snap["sync"] = api_get("/api/v1/diagnostics/sync")
    snap["errors"] = api_get("/api/v1/diagnostics/errors")
    snap["assets_top"] = api_get("/api/v1/assets?limit=5&sort_by=change_24h&sort_dir=desc")
    snap["anomalies"] = api_get("/api/v1/anomalies?limit=10&sort_by=detected_at&sort_dir=desc")
    snap["recommendations"] = api_get("/api/v1/recommendations?limit=10&status=active")
    snap["portfolio"] = api_get("/api/v1/portfolio/positions?status=open")
    snap["performance"] = api_get("/api/v1/recommendations/performance")
    snap["strategy"] = api_get("/api/v1/strategy/summary")

    # New endpoints from agent-built features
    snap["risk_metrics"] = api_get("/api/v1/portfolio/risk-metrics")

    # Print quick status
    sm = snap.get("summary", {}) if isinstance(snap.get("summary"), dict) else {}
    sched = sm.get("scheduler", {})
    recs = sm.get("recommendations", {})
    port = sm.get("portfolio", {})
    alerts = sm.get("alerts", {})
    print(f"  Jobs: {sched.get('total_jobs', '?')} | "
          f"Recs: {recs.get('active', '?')} | "
          f"Portfolio: {port.get('open', '?')} open/{port.get('closed', '?')} closed | "
          f"Anomalies: {alerts.get('unresolved_anomalies', '?')}", flush=True)

    return snap


def generate_audit_report(snapshots: list[dict], start_time: datetime.datetime, hours: float) -> str:
    end_time = datetime.datetime.now(datetime.timezone.utc)
    elapsed = end_time - start_time

    first = snapshots[0] if snapshots else {}
    last = snapshots[-1] if snapshots else {}

    def sg(snap, *keys, default="N/A"):
        val = snap
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k, default)
            else:
                return default
        return val if val is not None else default

    lines = []
    lines.append(f"# MarketPulse AI — 24h Audit Report")
    lines.append("")
    lines.append(f"**Start:** {start_time.strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"**End:** {end_time.strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"**Duration:** {str(elapsed).split('.')[0]}")
    lines.append(f"**Snapshots:** {len(snapshots)}")
    lines.append("")

    # 1. System Health
    lines.append("---")
    lines.append("## 1. System Health")
    lines.append("")
    lines.append(f"| Metric | Start | End |")
    lines.append(f"|--------|-------|-----|")
    lines.append(f"| Health | {sg(first, 'health', 'status')} | {sg(last, 'health', 'status')} |")
    lines.append(f"| Runtime | {sg(first, 'runtime', 'overall')} | {sg(last, 'runtime', 'overall')} |")

    last_errors = sg(last, "errors", "total_buffered", default=0)
    lines.append(f"| Errors in buffer | {sg(first, 'errors', 'total_buffered', default=0)} | {last_errors} |")
    lines.append("")

    # 2. Ingestion
    lines.append("---")
    lines.append("## 2. Data Ingestion")
    lines.append("")
    fs = first.get("summary", {}) if isinstance(first.get("summary"), dict) else {}
    ls = last.get("summary", {}) if isinstance(last.get("summary"), dict) else {}
    lines.append(f"| Metric | Start | End | Delta |")
    lines.append(f"|--------|-------|-----|-------|")
    j0 = fs.get("scheduler", {}).get("total_jobs", 0)
    j1 = ls.get("scheduler", {}).get("total_jobs", 0)
    lines.append(f"| Ingestion jobs | {j0} | {j1} | +{j1 - j0 if isinstance(j0, int) and isinstance(j1, int) else '?'} |")
    lines.append(f"| Last crypto | — | {ls.get('scheduler', {}).get('last_crypto_ingestion', 'N/A')[:19]} |  |")
    lines.append(f"| Last stock | — | {ls.get('scheduler', {}).get('last_stock_ingestion', 'N/A')[:19]} |  |")

    # Sync freshness
    last_sync = sg(last, "sync", "summary", default={})
    if isinstance(last_sync, dict):
        lines.append(f"| Fresh assets | {sg(first, 'sync', 'summary', 'fresh', default='?')} | {last_sync.get('fresh', '?')} |  |")
        lines.append(f"| Stale assets | {sg(first, 'sync', 'summary', 'stale', default='?')} | {last_sync.get('stale', '?')} |  |")
    lines.append("")

    # 3. Recommendations & Evaluation
    lines.append("---")
    lines.append("## 3. Recommendations & Evaluation")
    lines.append("")
    fr = fs.get("recommendations", {})
    lr = ls.get("recommendations", {})
    fe = fs.get("evaluation", {})
    le = ls.get("evaluation", {})
    lines.append(f"| Metric | Start | End |")
    lines.append(f"|--------|-------|-----|")
    lines.append(f"| Active recs | {fr.get('active', '?')} | {lr.get('active', '?')} |")
    lines.append(f"| Buy signals | {fr.get('buy_signals', '?')} | {lr.get('buy_signals', '?')} |")
    lines.append(f"| Evaluated (24h) | {fe.get('evaluated_24h', '?')} | {le.get('evaluated_24h', '?')} |")
    lines.append(f"| Last generated | — | {lr.get('last_generated', 'N/A')[:19]} |")
    lines.append("")

    # Performance metrics
    perf = last.get("performance", {})
    if isinstance(perf, dict) and not perf.get("_error"):
        lines.append("### Recommendation Performance")
        lines.append("")
        if "overall" in perf:
            o = perf["overall"]
            lines.append(f"- **Win rate (24h):** {o.get('win_rate_24h', 'N/A')}")
            lines.append(f"- **Avg return (24h):** {o.get('avg_return_24h', 'N/A')}")
            lines.append(f"- **Total evaluated:** {o.get('total_evaluated', 'N/A')}")
        if "by_type" in perf:
            lines.append("")
            lines.append("| Type | Count | Win Rate | Avg Return |")
            lines.append("|------|-------|----------|------------|")
            for t, d in perf["by_type"].items():
                lines.append(f"| {t} | {d.get('count', '?')} | {d.get('win_rate', '?')} | {d.get('avg_return', '?')} |")
        lines.append("")

    # 4. Portfolio
    lines.append("---")
    lines.append("## 4. Portfolio")
    lines.append("")
    fp = fs.get("portfolio", {})
    lp = ls.get("portfolio", {})
    lines.append(f"| Metric | Start | End |")
    lines.append(f"|--------|-------|-----|")
    lines.append(f"| Open positions | {fp.get('open', '?')} | {lp.get('open', '?')} |")
    lines.append(f"| Closed positions | {fp.get('closed', '?')} | {lp.get('closed', '?')} |")
    lines.append("")

    # Risk metrics
    risk = last.get("risk_metrics", {})
    if isinstance(risk, dict) and not risk.get("_error") and risk.get("equity"):
        lines.append("### Risk Metrics")
        lines.append("")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        for k, v in risk.items():
            if k != "_error":
                lines.append(f"| {k} | {v} |")
        lines.append("")

    # 5. Anomalies
    lines.append("---")
    lines.append("## 5. Anomalies")
    lines.append("")
    fa = fs.get("alerts", fs.get("summary", {}).get("alerts", {})) if isinstance(fs, dict) else {}
    la = ls.get("summary", {}).get("alerts", {}) if isinstance(ls.get("summary"), dict) else {}
    lines.append(f"| Metric | Start | End |")
    lines.append(f"|--------|-------|-----|")
    lines.append(f"| Unresolved | {fa.get('unresolved_anomalies', '?')} | {la.get('unresolved_anomalies', '?')} |")
    lines.append(f"| Unread alerts | {fa.get('unread', '?')} | {la.get('unread', '?')} |")
    lines.append("")

    last_anom = last.get("anomalies", {})
    if isinstance(last_anom, dict) and last_anom.get("items"):
        lines.append("### Recent Anomalies")
        lines.append("")
        lines.append("| Symbol | Type | Severity | Score | Detected |")
        lines.append("|--------|------|----------|-------|----------|")
        for a in last_anom["items"][:10]:
            lines.append(f"| {a.get('asset_symbol', '?')} | {a.get('anomaly_type', '?')} | {a.get('severity', '?')} | {a.get('score', '?')} | {str(a.get('detected_at', '?'))[:16]} |")
        lines.append("")

    # 6. Strategy
    lines.append("---")
    lines.append("## 6. Strategy State")
    lines.append("")
    strat = last.get("strategy", {})
    if isinstance(strat, dict) and not strat.get("_error"):
        lines.append(f"- **Profile:** {sg(strat, 'profile', 'name')}")
        lines.append(f"- **Regime:** {sg(strat, 'regime', 'regime')}")
        lines.append(f"- **Auto-switch:** {'enabled' if sg(strat, 'auto_switch', 'enabled') else 'disabled'}")
        lines.append(f"- **Recommended:** {sg(strat, 'auto_switch', 'recommended_profile')}")
        eff = strat.get("effective", {})
        if eff:
            lines.append(f"- **Effective threshold:** {eff.get('candidate_buy_threshold', '?')}")
            lines.append(f"- **Effective max position:** {eff.get('max_position_pct', '?')}")
    lines.append("")

    # 7. Timeline
    lines.append("---")
    lines.append("## 7. Timeline")
    lines.append("")
    lines.append("| Time | Health | Jobs | Recs | Open Pos | Anomalies |")
    lines.append("|------|--------|------|------|----------|-----------|")
    for s in snapshots:
        ts = str(s.get("timestamp", "?"))[:16]
        h = sg(s, "health", "status")
        sm = s.get("summary", {}) if isinstance(s.get("summary"), dict) else {}
        jobs = sm.get("scheduler", {}).get("total_jobs", "?")
        recs = sm.get("recommendations", {}).get("active", "?")
        port = sm.get("portfolio", {}).get("open", "?")
        anom = sm.get("alerts", {}).get("unresolved_anomalies", "?")
        lines.append(f"| {ts} | {h} | {jobs} | {recs} | {port} | {anom} |")
    lines.append("")

    # 8. Optimization Suggestions
    lines.append("---")
    lines.append("## 8. Optimization Suggestions")
    lines.append("")
    suggestions = []

    # Check if errors accumulated
    if isinstance(last_errors, int) and last_errors > 10:
        suggestions.append(f"- **Error buffer has {last_errors} errors** — check /diagnostics/errors for recurring issues")

    # Check stale data
    if isinstance(last_sync, dict) and last_sync.get("stale", 0) > 0:
        suggestions.append(f"- **{last_sync['stale']} stale asset(s)** — ingestion may be failing for some symbols")

    # Check recommendation accuracy
    if isinstance(perf, dict) and "overall" in perf:
        wr = perf["overall"].get("win_rate_24h")
        if isinstance(wr, (int, float)) and wr < 0.4:
            suggestions.append(f"- **Low win rate ({wr:.1%})** — consider tuning scoring weights or thresholds")

    # Check if portfolio is idle
    if isinstance(lp, dict) and lp.get("open", 0) == 0 and lp.get("closed", 0) == ls.get("portfolio", {}).get("closed", 0):
        suggestions.append("- **No portfolio activity** — threshold may be too high or no buy signals generated")

    # Check anomaly flood
    if isinstance(la, dict) and la.get("unresolved_anomalies", 0) > 50:
        suggestions.append(f"- **{la['unresolved_anomalies']} unresolved anomalies** — consider raising z-score thresholds")

    if not suggestions:
        suggestions.append("- No critical issues detected. System operating normally.")

    lines.extend(suggestions)
    lines.append("")

    lines.append("---")
    lines.append(f"*Report generated: {end_time.strftime('%Y-%m-%d %H:%M UTC')}*")
    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="24h MarketPulse Audit Monitor")
    parser.add_argument("--hours", type=float, default=24, help="Duration in hours (default: 24)")
    args = parser.parse_args()

    total_minutes = int(args.hours * 60)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"=== MarketPulse AI — {args.hours}h Audit Monitor ===", flush=True)
    print(f"Snapshots every {SNAPSHOT_INTERVAL_MIN} min for {total_minutes} min", flush=True)
    print(f"Backend must be running at {BASE_URL}", flush=True)
    print("", flush=True)

    if not check_backend():
        print("ERROR: Backend not responding. Start it first:", flush=True)
        print("  cd backend && .venv\\Scripts\\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000", flush=True)
        sys.exit(1)

    print("Backend OK. Starting monitor...\n", flush=True)

    start_time = datetime.datetime.now(datetime.timezone.utc)
    snapshots = []

    try:
        snapshots.append(take_snapshot("START"))
        elapsed = 0

        while elapsed < total_minutes:
            sleep_min = min(SNAPSHOT_INTERVAL_MIN, total_minutes - elapsed)
            print(f"\n--- Sleeping {sleep_min} min ({elapsed}/{total_minutes} min elapsed) ---", flush=True)
            time.sleep(sleep_min * 60)
            elapsed += sleep_min

            if not check_backend():
                print("WARNING: Backend not responding! Waiting 60s...", flush=True)
                time.sleep(60)
                if not check_backend():
                    print("ERROR: Backend down. Taking final snapshot.", flush=True)
                    break

            snapshots.append(take_snapshot(f"T+{elapsed}min"))

    except KeyboardInterrupt:
        print("\n\nInterrupted. Taking final snapshot...", flush=True)
        try:
            snapshots.append(take_snapshot("INTERRUPTED"))
        except Exception:
            pass

    # Generate report
    print(f"\n=== Generating audit report ({len(snapshots)} snapshots) ===", flush=True)
    report_md = generate_audit_report(snapshots, start_time, args.hours)

    ts_str = start_time.strftime("%Y%m%d_%H%M%S")
    report_path = REPORT_DIR / f"audit_report_{ts_str}.md"
    report_path.write_text(report_md, encoding="utf-8")

    json_path = REPORT_DIR / f"audit_snapshots_{ts_str}.json"
    json_path.write_text(json.dumps(snapshots, indent=2, default=str), encoding="utf-8")

    print(f"\nReport: {report_path}", flush=True)
    print(f"Data: {json_path}", flush=True)
    print("=== Done ===", flush=True)


if __name__ == "__main__":
    main()

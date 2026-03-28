"""Smoke test — verify MarketPulse AI backend health end-to-end.

Covers: health, crypto assets, stock assets, OHLCV, indicators,
anomalies, alerts, reports, diagnostics.

Usage:
    python scripts/smoke_test.py [BASE_URL]

Default BASE_URL: http://localhost:8000
"""

from __future__ import annotations

import json
import sys
import urllib.request
import urllib.error

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
passed = 0
failed = 0
skipped = 0
errors: list[str] = []


def check(name: str, method: str, path: str, expect_fn=None, body: str | None = None):
    global passed, failed
    url = f"{BASE}{path}"
    try:
        req = urllib.request.Request(url, method=method)
        if body:
            req.data = body.encode()
            req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            if expect_fn:
                result = expect_fn(data)
                if result is not True:
                    failed += 1
                    msg = f"FAIL  {name}: {result}"
                    errors.append(msg)
                    print(f"  {msg}")
                    return data
            passed += 1
            print(f"  PASS  {name}")
            return data
    except urllib.error.HTTPError as e:
        failed += 1
        msg = f"FAIL  {name}: HTTP {e.code}"
        errors.append(msg)
        print(f"  {msg}")
        return None
    except Exception as e:
        failed += 1
        msg = f"FAIL  {name}: {e}"
        errors.append(msg)
        print(f"  {msg}")
        return None


def skip(name: str, reason: str):
    global skipped
    skipped += 1
    print(f"  SKIP  {name} — {reason}")


def _get_first_asset_id(asset_class: str) -> str | None:
    """Fetch first asset ID for a given class."""
    try:
        url = f"{BASE}/api/v1/assets?asset_class={asset_class}&limit=1"
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read())
            if data.get("items"):
                return data["items"][0]["id"]
    except Exception:
        pass
    return None


def main():
    print(f"\n{'=' * 50}")
    print(f"  MarketPulse AI — Mixed-Asset Smoke Test")
    print(f"  Target: {BASE}")
    print(f"{'=' * 50}\n")

    # ── Core ──────────────────────────────────────
    print("── Core ──")
    check(
        "Health check",
        "GET", "/api/v1/health",
        lambda d: True if d.get("status") == "ok" else f"status={d.get('status')}",
    )

    check(
        "Assets list (all)",
        "GET", "/api/v1/assets?limit=5",
        lambda d: True if d.get("total", 0) > 0 else "no assets found",
    )

    check(
        "Assets list (crypto filter)",
        "GET", "/api/v1/assets?asset_class=crypto&limit=3",
        lambda d: True if d.get("total", 0) > 0 else "no crypto assets",
    )

    check(
        "Assets list (stock filter)",
        "GET", "/api/v1/assets?asset_class=stock&limit=3",
        lambda d: True if d.get("total", 0) > 0 else "no stock assets",
    )

    check(
        "Asset search (BTC)",
        "GET", "/api/v1/assets/search?q=btc",
        lambda d: True if isinstance(d, list) else "not a list",
    )

    check(
        "Asset search (AAPL)",
        "GET", "/api/v1/assets/search?q=aapl",
        lambda d: True if isinstance(d, list) else "not a list",
    )

    # ── Crypto asset detail ───────────────────────
    print("\n── Crypto Asset ──")
    crypto_id = _get_first_asset_id("crypto")

    if crypto_id:
        check(
            "Crypto detail",
            "GET", f"/api/v1/assets/{crypto_id}",
            lambda d: True if d.get("asset_class") == "crypto" else f"class={d.get('asset_class')}",
        )

        check(
            "Crypto OHLCV",
            "GET", f"/api/v1/assets/{crypto_id}/ohlcv?interval=1h&limit=5",
            lambda d: True if isinstance(d, list) and len(d) > 0 else "no bars",
        )

        check(
            "Crypto indicators",
            "GET", f"/api/v1/assets/{crypto_id}/indicators?interval=1h",
            lambda d: True if d.get("rsi_14") is not None else "rsi_14 missing (need 35+ bars)",
        )

        check(
            "Crypto anomalies",
            "GET", f"/api/v1/assets/{crypto_id}/anomalies?limit=5",
            lambda d: True if isinstance(d, list) else "not a list",
        )
    else:
        skip("Crypto detail / OHLCV / indicators", "no crypto assets in DB")

    # ── Stock asset detail ────────────────────────
    print("\n── Stock Asset ──")
    stock_id = _get_first_asset_id("stock")

    if stock_id:
        check(
            "Stock detail",
            "GET", f"/api/v1/assets/{stock_id}",
            lambda d: (
                True if d.get("asset_class") == "stock" and d.get("exchange")
                else f"class={d.get('asset_class')} exchange={d.get('exchange')}"
            ),
        )

        check(
            "Stock OHLCV",
            "GET", f"/api/v1/assets/{stock_id}/ohlcv?interval=1h&limit=5",
            lambda d: True if isinstance(d, list) and len(d) > 0 else "no bars (run stock ingestion first)",
        )

        check(
            "Stock indicators",
            "GET", f"/api/v1/assets/{stock_id}/indicators?interval=1h",
            lambda d: True if d.get("rsi_14") is not None else "rsi_14 missing (need 35+ bars)",
        )
    else:
        skip("Stock detail / OHLCV / indicators", "no stock assets in DB")

    # ── Signals ───────────────────────────────────
    print("\n── Signals ──")
    check(
        "Anomalies list",
        "GET", "/api/v1/anomalies?limit=5",
        lambda d: True if "items" in d else "missing items key",
    )

    check(
        "Anomaly stats",
        "GET", "/api/v1/anomalies/stats",
        lambda d: True if "total" in d and "unresolved" in d else "missing keys",
    )

    check(
        "Alert stats",
        "GET", "/api/v1/alerts/stats",
        lambda d: True if "total_events" in d else "missing total_events",
    )

    check(
        "Alert rules",
        "GET", "/api/v1/alerts/rules",
        lambda d: True if isinstance(d, list) else "not a list",
    )

    check(
        "Reports list",
        "GET", "/api/v1/reports?limit=5",
        lambda d: True if "items" in d else "missing items key",
    )

    # ── Ingestion ─────────────────────────────────
    print("\n── Ingestion ──")
    check(
        "Ingestion status",
        "GET", "/api/v1/ingestion/status",
        lambda d: True if "recent_jobs" in d and "sync_states" in d else "missing keys",
    )

    check(
        "Price bar counts",
        "GET", "/api/v1/price-bars/count",
        lambda d: True if isinstance(d, list) else "not a list",
    )

    # ── Diagnostics ───────────────────────────────
    print("\n── Diagnostics ──")
    check(
        "Diagnostics config",
        "GET", "/api/v1/diagnostics/config",
        lambda d: True if "app_env" in d and "scheduler_enabled" in d else "missing keys",
    )

    check(
        "Diagnostics sync",
        "GET", "/api/v1/diagnostics/sync",
        lambda d: True if "summary" in d and "items" in d else "missing keys",
    )

    check(
        "Diagnostics errors",
        "GET", "/api/v1/diagnostics/errors",
        lambda d: True if "total_buffered" in d else "missing total_buffered",
    )

    # ── Summary ───────────────────────────────────
    total = passed + failed
    print(f"\n{'=' * 50}")
    print(f"  Results: {passed} passed, {failed} failed, {skipped} skipped ({total} total)")

    if errors:
        print(f"\n  Failures:")
        for e in errors:
            print(f"    {e}")

    if failed == 0:
        print(f"\n  All checks passed.")
    print()

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()

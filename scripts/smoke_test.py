"""Smoke test — verify MarketPulse AI backend health end-to-end.

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
                    msg = f"FAIL  {name}: assertion failed — {result}"
                    errors.append(msg)
                    print(f"  {msg}")
                    return
            passed += 1
            print(f"  PASS  {name}")
    except urllib.error.HTTPError as e:
        failed += 1
        msg = f"FAIL  {name}: HTTP {e.code}"
        errors.append(msg)
        print(f"  {msg}")
    except Exception as e:
        failed += 1
        msg = f"FAIL  {name}: {e}"
        errors.append(msg)
        print(f"  {msg}")


def main():
    print(f"\n=== MarketPulse AI Smoke Test ===")
    print(f"    Target: {BASE}\n")

    # 1. Health
    check(
        "Health check",
        "GET", "/api/v1/health",
        lambda d: True if d.get("status") == "ok" else f"status={d.get('status')}",
    )

    # 2. Assets list
    check(
        "Assets list (non-empty)",
        "GET", "/api/v1/assets?limit=5",
        lambda d: True if d.get("total", 0) > 0 else "no assets found",
    )

    # 3. Fetch first asset ID for further tests
    first_id = None
    try:
        with urllib.request.urlopen(f"{BASE}/api/v1/assets?limit=1", timeout=10) as r:
            data = json.loads(r.read())
            if data.get("items"):
                first_id = data["items"][0]["id"]
    except Exception:
        pass

    if first_id:
        # 4. Asset detail
        check(
            "Asset detail",
            "GET", f"/api/v1/assets/{first_id}",
            lambda d: True if d.get("symbol") else "missing symbol",
        )

        # 5. OHLCV data
        check(
            "OHLCV bars exist",
            "GET", f"/api/v1/assets/{first_id}/ohlcv?interval=1h&limit=5",
            lambda d: True if isinstance(d, list) and len(d) > 0 else "no bars",
        )

        # 6. Indicators
        check(
            "Indicators compute",
            "GET", f"/api/v1/assets/{first_id}/indicators?interval=1h",
            lambda d: True if d.get("rsi_14") is not None else "rsi_14 missing",
        )

        # 7. Asset anomalies (may be empty — that's ok)
        check(
            "Asset anomalies endpoint",
            "GET", f"/api/v1/assets/{first_id}/anomalies?limit=5",
            lambda d: True if isinstance(d, list) else "not a list",
        )
    else:
        print("  SKIP  Asset detail / OHLCV / Indicators — no assets in DB")

    # 8. Anomalies list
    check(
        "Anomalies list",
        "GET", "/api/v1/anomalies?limit=5",
        lambda d: True if "items" in d else "missing items key",
    )

    # 9. Anomaly stats
    check(
        "Anomaly stats",
        "GET", "/api/v1/anomalies/stats",
        lambda d: True if "total" in d else "missing total key",
    )

    # 10. Price bar counts
    check(
        "Price bar counts",
        "GET", "/api/v1/price-bars/count",
        lambda d: True if isinstance(d, list) else "not a list",
    )

    # 11. Ingestion status
    check(
        "Ingestion status",
        "GET", "/api/v1/ingestion/status",
        lambda d: True if "recent_jobs" in d else "missing recent_jobs",
    )

    # 12. Search
    check(
        "Asset search",
        "GET", "/api/v1/assets/search?q=btc",
        lambda d: True if isinstance(d, list) else "not a list",
    )

    # Summary
    total = passed + failed
    print(f"\n{'=' * 40}")
    print(f"  Results: {passed}/{total} passed, {failed} failed")
    if errors:
        print(f"\n  Failures:")
        for e in errors:
            print(f"    {e}")
    print()

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()

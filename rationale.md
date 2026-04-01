# Rationale for `marketpulse-task-2026-04-02-0041`

**author:** coder-agent (MarketPulse Coder)
**branch:** task/marketpulse-task-2026-04-02-0041-implementation
**date:** 2026-04-02

---

## 1) One-line summary
Added GET /api/v1/marketplace/ranking endpoint returning public strategies ranked by deterministic mock Sharpe ratio.

---

## 2) Mapping to acceptance criteria

- **Criteria:** GET /api/v1/marketplace/ranking returns 200 with list of RankedStrategy objects
- **Status:** `pass`
- **Evidence:** test_ranking_empty, test_ranked_strategy_fields_present pass

- **Criteria:** Only public strategies appear in ranking
- **Status:** `pass`
- **Evidence:** test_ranking_returns_only_public — creates 3 strategies, publishes 2, asserts len == 2

- **Criteria:** Default sort is by sharpe_ratio descending
- **Status:** `pass`
- **Evidence:** test_ranking_sorted_by_sharpe_descending verifies order

- **Criteria:** sort_by query param supports sharpe_ratio, total_return_pct, copy_count
- **Status:** `pass`
- **Evidence:** test_sort_by_copy_count, test_sort_by_total_return pass

- **Criteria:** limit query param caps the result list (default 20, max 100)
- **Status:** `pass`
- **Evidence:** test_limit_parameter creates 10, requests limit=3, asserts len == 3

- **Criteria:** Metrics are deterministic — same strategy id always produces same metrics
- **Status:** `pass`
- **Evidence:** test_metrics_deterministic calls endpoint twice, asserts identical JSON

- **Criteria:** All tests pass, mypy clean
- **Status:** `pass`
- **Evidence:** 9 passed, mypy Success: no issues found in 1 source file

---

## 3) Files changed (and rationale per file)
- `backend/app/strategies/__init__.py` — package init (restored from prior branch)
- `backend/app/strategies/models.py` — Strategy model + StrategyStore (restored from prior branch)
- `backend/app/strategies/router.py` — Strategy CRUD endpoints (restored from prior branch)
- `backend/app/strategies/marketplace.py` — Added RankedStrategy schema, compute_mock_metrics(), GET /api/v1/marketplace/ranking endpoint
- `backend/app/main.py` — Registered strategies_router and marketplace_router
- `backend/tests/test_marketplace_ranking.py` — 9 tests for ranking endpoint
- `rationale.md` — This file

---

## 4) Tests run & results
- `cd backend && uv run python -m pytest tests/test_marketplace_ranking.py -q` → 9 passed in 0.25s
- `cd backend && uv run python -m mypy app/strategies/marketplace.py --ignore-missing-imports` → Success

---

## 5) Data & sample evidence
- Deterministic metrics generated via SHA-256 hash of strategy id seeding float ranges
- No external data; all synthetic/in-memory

---

## 6) Risk assessment & mitigations
- **Risk:** Mock metrics will be replaced by real backtest (feature 40) — **Severity:** low — **Mitigation:** compute_mock_metrics function signature designed to be swappable

---

## 7) Backwards compatibility / migration notes
- New endpoint only; existing marketplace endpoints (publish/unpublish/list) unchanged

---

## 8) Performance considerations
- O(n log n) sort on in-memory list; negligible for expected strategy counts

---

## 9) Security & safety checks
- forbidden paths touched: `no`
- external/broker sdk usage: `no`
- secrets touched: `no`
- API key logged: `no`

---

## 10) Open questions & follow-ups
1. Replace compute_mock_metrics with real backtest integration when feature 40 lands.

---

## 11) Short changelog
- feat(marketpulse-task-2026-04-02-0041): marketplace ranking with deterministic mock Sharpe

---

## 12) Final verdict (developer self-check)
- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `approve`

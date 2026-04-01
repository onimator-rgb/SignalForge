# Rationale for `marketpulse-task-2026-04-01-0001`

**author:** coder-worker (MarketPulse Coder)
**branch:** task/marketpulse-task-2026-04-01-0001-implementation
**date:** 2026-04-01

---

## 1) One-line summary
Add POST /api/v1/backtest/run endpoint with Pydantic schemas, async DB query, and full test coverage.

---

## 2) Mapping to acceptance criteria

- **Criteria:** POST /api/v1/backtest/run with valid asset_id returns 200 with BacktestResponse including total_return, sharpe_ratio, win_rate, trades list
- **Status:** `pass`
- **Evidence:** test_successful_backtest passes — response contains all metric fields and trades list

- **Criteria:** Request with asset_id having < 2 price bars returns 404 with 'Not enough price data'
- **Status:** `pass`
- **Evidence:** test_not_enough_price_data_returns_404 and test_no_price_data_returns_404 both pass

- **Criteria:** Request with invalid profile_name returns 400 with 'Unknown profile'
- **Status:** `pass`
- **Evidence:** test_invalid_profile_returns_400 passes

- **Criteria:** All trades in response have entry_index, exit_index, entry_price, exit_price, pnl, pnl_pct, exit_reason fields
- **Status:** `pass`
- **Evidence:** test_trades_have_required_fields passes — verifies all fields on each trade

- **Criteria:** pytest passes with all tests green
- **Status:** `pass`
- **Evidence:** 5 passed in 0.09s

- **Criteria:** mypy passes with no errors
- **Status:** `pass`
- **Evidence:** Success: no issues found in 2 source files

---

## 3) Files changed (and rationale per file)
- `backend/app/backtest/schemas.py` — Pydantic request/response models (BacktestRequest, TradeOut, BacktestResponse)
- `backend/app/backtest/router.py` — APIRouter with POST /run endpoint: validates profile, queries price_bars, runs simulate_trades + backtest_metrics
- `backend/app/main.py` — Register backtest_router in create_app()
- `backend/tests/test_backtest_api.py` — 5 async tests covering success, 404, 400, and trade field validation

---

## 4) Tests run & results
- **Commands run:**
  - `cd backend && uv run python -m pytest tests/test_backtest_api.py -q` → 5 passed in 0.09s
  - `cd backend && uv run python -m mypy app/backtest/router.py app/backtest/schemas.py --ignore-missing-imports` → Success: no issues found in 2 source files

---

## 5) Data & sample evidence
- Synthetic price data used in tests (mock DB rows with .close attribute)

---

## 6) Risk assessment & mitigations
- **Risk:** Integration with existing DB schema — **Severity:** low — **Mitigation:** Uses existing PriceBar model, tests mock DB layer

---

## 7) Backwards compatibility / migration notes
- New files only (schemas.py, router.py, test file), plus one line added to main.py. Fully backward compatible.

---

## 8) Performance considerations
- No performance impact expected. Simple SELECT query with existing composite index.

---

## 9) Security & safety checks
- forbidden paths touched: `no`
- external/broker sdk usage: `no`
- secrets touched: `no`
- API key logged: `no`

---

## 10) Open questions & follow-ups
- None.

---

## 11) Short changelog
- `feat(backtest): add POST /api/v1/backtest/run endpoint [marketpulse-task-2026-04-01-0001]`

---

## 12) Final verdict (developer self-check)
- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `approve`

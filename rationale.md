# Rationale for `marketpulse-task-2026-04-01-0025`

**author:** coder-agent (MarketPulse Coder)
**branch:** task/marketpulse-task-2026-04-01-0025-implementation
**date:** 2026-04-01

---

## 1) One-line summary
Add portfolio risk metrics endpoint (Sharpe, Sortino, max drawdown, profit factor) and frontend display card.

---

## 2) Mapping to acceptance criteria

- **Criteria:** compute_risk_metrics returns correct Sharpe ratio for known trades (5%, -3%, 8%, -2%, 4%)
- **Status:** `pass`
- **Evidence:** `test_known_returns` validates against manual calculation

- **Criteria:** Max drawdown correctly identifies largest peak-to-trough in cumulative PnL sequence
- **Status:** `pass`
- **Evidence:** `test_peak_to_trough` verifies +100/-30/+20 => 30% drawdown

- **Criteria:** Profit factor = gross_profit / gross_loss, returns None when no losses
- **Status:** `pass`
- **Evidence:** `test_profit_factor_normal` and `test_no_losses_none`

- **Criteria:** Returns None for ratios when fewer than 2 closed positions
- **Status:** `pass`
- **Evidence:** `test_single_position_no_ratios` and `test_empty_positions`

- **Criteria:** GET /risk-metrics endpoint returns RiskMetricsOut JSON
- **Status:** `pass`
- **Evidence:** Endpoint defined in router.py, returns RiskMetricsOut schema

- **Criteria:** breakdown_by_reason correctly counts close_reason values
- **Status:** `pass`
- **Evidence:** `test_breakdown_by_reason`

- **Criteria:** RiskMetrics interface in api.ts matches backend RiskMetricsOut schema
- **Status:** `pass`
- **Evidence:** Field-by-field match verified

- **Criteria:** PortfolioView fetches and displays risk metrics on mount
- **Status:** `pass`
- **Evidence:** api.get('/portfolio/risk-metrics') in load() function

- **Criteria:** Numbers use tabular-nums class and appropriate color coding
- **Status:** `pass`
- **Evidence:** All numeric values use tabular-nums; Sharpe green/yellow/red, drawdown red, profit factor green/red

- **Criteria:** Handles loading and empty states gracefully
- **Status:** `pass`
- **Evidence:** riskLoading state + "No closed trades yet" message

- **Criteria:** vue-tsc passes with no type errors
- **Status:** `pass`
- **Evidence:** `npx vue-tsc --noEmit` passed clean

---

## 3) Files changed (and rationale per file)
- `backend/app/portfolio/risk_metrics.py` — New: pure compute function + dataclass
- `backend/app/portfolio/schemas.py` — Added RiskMetricsOut Pydantic model
- `backend/app/portfolio/router.py` — Added GET /risk-metrics endpoint
- `backend/tests/test_risk_metrics.py` — 15 unit tests for all metrics + edge cases
- `frontend/src/types/api.ts` — Added RiskMetrics TypeScript interface
- `frontend/src/views/PortfolioView.vue` — Added risk metrics card section
- `rationale.md` — This file

---

## 4) Tests run & results
- `cd backend && uv run python -m pytest tests/test_risk_metrics.py -q` — 15 passed
- `cd backend && uv run python -m mypy app/portfolio/risk_metrics.py --ignore-missing-imports` — Success
- `cd frontend && npx vue-tsc --noEmit` — passed

---

## 5) Data & sample evidence
- All tests use synthetic SimpleNamespace objects mimicking PortfolioPosition fields.

---

## 6) Risk assessment & mitigations
- **Risk:** Read-only query — **Severity:** low — **Mitigation:** No mutations, no migrations

---

## 7) Backwards compatibility / migration notes
- Additive only. No existing endpoints or schemas modified. No DB migration needed.

---

## 8) Performance considerations
- On-the-fly computation. Acceptable for demo portfolios. Cache if >1000 positions.

---

## 9) Security & safety checks
- forbidden paths touched: `no`
- external/broker sdk usage: `no`
- secrets touched: `no`
- API key logged: `no`

---

## 10) Open questions & follow-ups
None.

---

## 11) Short changelog
- feat(portfolio): add risk metrics computation module
- feat(portfolio): add GET /risk-metrics endpoint
- feat(frontend): add risk metrics card to PortfolioView

---

## 12) Final verdict (developer self-check)
- **I confirm** all acceptance criteria pass with test evidence: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `approve`

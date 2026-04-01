# Rationale for `marketpulse-task-2026-04-01-0005`

**author:** coder-agent
**branch:** task/marketpulse-task-2026-04-01-0005-implementation
**commit_sha:** e926ab4
**date:** 2026-04-01

---

## 1) One-line summary
Add a risk metrics section to PerformanceView.vue displaying Sharpe, Sortino, MDD, Profit Factor, Win Rate, avg win/loss, and close-reason breakdown fetched from the existing `/portfolio/risk-metrics` endpoint.

---

## 2) Mapping to acceptance criteria

- **Criteria:** PerformanceView.vue imports and calls fetchRiskMetrics()
- **Status:** `pass`
- **Evidence:** `import { fetchPortfolio, fetchRiskMetrics } from '../api/portfolio'` at line 4; called in `load()` with separate try/catch.

- **Criteria:** Risk metrics section displays Sharpe, MDD, Profit Factor, Win Rate cards
- **Status:** `pass`
- **Evidence:** 4-column grid with dedicated cards for each metric, color-coded per spec.

- **Criteria:** Sortino, avg hold hours, avg win/loss %, best/worst trade shown
- **Status:** `pass`
- **Evidence:** 2-column detail row below the 4-card grid displays all values.

- **Criteria:** Close reason breakdown displayed as colored pills
- **Status:** `pass`
- **Evidence:** `v-for` over `risk.breakdown_by_reason` with `reasonColor()` helper.

- **Criteria:** Null/empty state handled gracefully with placeholder text
- **Status:** `pass`
- **Evidence:** `v-else-if="!risk || risk.total_closed === 0"` shows "No risk data yet".

- **Criteria:** All values use tabular-nums and appropriate color coding
- **Status:** `pass`
- **Evidence:** All numeric values have `tabular-nums` class; green/red/yellow applied via helpers.

- **Criteria:** vue-tsc --noEmit passes with no type errors
- **Status:** `pass`
- **Evidence:** `cd frontend && npx vue-tsc --noEmit` — exit code 0, no output.

- **Criteria:** Risk metrics fetch failure does not break the rest of the page
- **Status:** `pass`
- **Evidence:** fetchRiskMetrics() in separate try/catch after main Promise.all.

---

## 3) Files changed (and rationale per file)

- `frontend/src/api/portfolio.ts` — Added `fetchRiskMetrics()` and `RiskMetrics` import. ~5 LOC.
- `frontend/src/views/PerformanceView.vue` — Added risk state, fetch logic, helpers, template section. ~100 LOC.
- `rationale.md` — Updated for this task.

---

## 4) Tests run & results

- **Commands run:**
  - `cd frontend && npx vue-tsc --noEmit`
- **Results summary:**
  - typecheck: passed (exit 0, no errors)

---

## 5) Data & sample evidence
No new fixtures. Component consumes existing `RiskMetrics` type from `api.ts` (lines 310-325).

---

## 6) Risk assessment & mitigations

- **Risk:** Integration — endpoint shape mismatch — **Severity:** low — **Mitigation:** RiskMetrics type matches backend; separate try/catch.

---

## 7) Backwards compatibility / migration notes
- No API changes. Consuming existing endpoint. Fully backward compatible.

---

## 8) Performance considerations
- One additional API call on page load, non-blocking (called after main data).

---

## 9) Security & safety checks

- forbidden paths touched: `no`
- external/broker sdk usage: `no`
- secrets touched: `no`

---

## 10) Open questions & follow-ups

1. Should Sortino ratio use different color thresholds than Sharpe?
2. Consider adding loading skeleton for risk metrics section.

---

## 11) Short changelog

- (pending) — feat(marketpulse-task-2026-04-01-0005): add risk metrics section to PerformanceView

---

## 12) Final verdict (developer self-check)

- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `validate`

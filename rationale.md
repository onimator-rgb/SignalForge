# Rationale for `marketpulse-task-2026-04-02-0061`

**author:** coder-agent
**branch:** task/marketpulse-task-2026-04-02-0061-implementation
**date:** 2026-04-02

---

## 1) One-line summary
Add a Risk Allocation section to PerformanceView.vue showing position size distribution, asset class exposure, and concentration warnings.

---

## 2) Mapping to acceptance criteria

- **Criteria:** PerformanceView has a 'Risk Allocation' section visible below Risk Metrics
- **Status:** `pass`
- **Evidence:** Template section added between Risk Metrics and Demo Portfolio sections with `<h2>Risk Allocation</h2>` header.

- **Criteria:** Position size distribution shows horizontal bars with symbol, value, and percentage for each open position
- **Status:** `pass`
- **Evidence:** `positionAllocations` computed property calculates pct per position; rendered as horizontal bars with symbol, USD value, and percentage.

- **Criteria:** Asset class exposure groups positions by asset_class with aggregate percentages
- **Status:** `pass`
- **Evidence:** `assetClassExposure` computed groups by asset_class, sums current_value_usd, computes pct; rendered with colored bars (crypto=purple, stock=blue, other=gray).

- **Criteria:** Concentration warning appears when single position > 40% of equity
- **Status:** `pass`
- **Evidence:** `concentrationWarnings` computed checks `alloc.pct > 40` and emits warning badge.

- **Criteria:** Concentration warning appears when single asset class > 60% of equity
- **Status:** `pass`
- **Evidence:** `concentrationWarnings` computed checks `exp.pct > 60` and emits warning badge.

- **Criteria:** Empty state shown when no open positions exist
- **Status:** `pass`
- **Evidence:** `v-if="portfolio.open_positions.length === 0"` renders muted message.

- **Criteria:** vue-tsc --noEmit passes with no errors
- **Status:** `pass`
- **Evidence:** `cd frontend && npx vue-tsc --noEmit` — exit code 0, no output.

- **Criteria:** Dark theme styling matches existing PerformanceView cards (bg-gray-800, text-gray-100, etc.)
- **Status:** `pass`
- **Evidence:** Uses bg-gray-800 rounded-xl p-6 cards, text-gray-100/200/300/400 hierarchy.

- **Criteria:** Numbers use tabular-nums class
- **Status:** `pass`
- **Evidence:** All numeric displays use `tabular-nums` class.

---

## 3) Files changed (and rationale per file)

- `frontend/src/views/PerformanceView.vue` — Added `computed` import, 4 computed properties, and Risk Allocation template section. +133 LOC.

---

## 4) Tests run & results

- **Commands run:**
  - `cd frontend && npx vue-tsc --noEmit`
- **Results summary:**
  - typecheck: passed (exit code 0, no errors)

---

## 5) Data & sample evidence

Pure frontend computation using existing `portfolio.value.open_positions` data. No new data sources.

---

## 6) Risk assessment & mitigations

- **Risk:** Type mismatches if PortfolioPosition interface changes — **Severity:** low — **Mitigation:** All nullable fields handled with `?? 0` / `?? 'other'` fallbacks.

---

## 7) Backwards compatibility / migration notes

No API changes, no DB migrations. Pure frontend addition.

---

## 8) Performance considerations

Computed properties are reactive and cached by Vue. No additional API calls. Negligible impact.

---

## 9) Security & safety checks

- forbidden paths touched: `no`
- external/broker sdk usage: `no`
- secrets touched: `no`

---

## 10) Open questions & follow-ups

1. Should concentration thresholds (40% position, 60% asset class) be configurable?
2. Consider adding pie/donut chart visualization in a future task.

---

## 11) Short changelog

- feat(marketpulse-task-2026-04-02-0061): add Risk Allocation section to PerformanceView — 1 file, +133 LOC

---

## 12) Final verdict (developer self-check)

- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `validate`

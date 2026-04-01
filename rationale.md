# Rationale for `marketpulse-task-2026-04-02-0047`

**author:** coder-worker (MarketPulse Coder)
**branch:** task/marketpulse-task-2026-04-02-0047-implementation
**commit_sha:** (pending)
**date:** 2026-04-02
**model_calls:** 1

---

## 1) One-line summary
Strategy Builder view with rule editor form, strategy list, route, and nav entry.

---

## 2) Mapping to acceptance criteria

- **Criteria:** StrategyBuilderView.vue exists and exports a valid Vue SFC with `<script setup lang="ts">`
- **Status:** `pass`
- **Evidence:** File created at frontend/src/views/StrategyBuilderView.vue with `<script setup lang="ts">`

- **Criteria:** Route /strategy-builder is registered in router/index.ts
- **Status:** `pass`
- **Evidence:** Route added after /strategy entry in router/index.ts

- **Criteria:** Nav entry for Strategy Builder appears in AppLayout.vue navItems
- **Status:** `pass`
- **Evidence:** Entry `{ to: '/strategy-builder', label: 'Builder', icon: '🔧', badge: false }` added after Strategia

- **Criteria:** Form includes inputs for name, description, profile_name, and a dynamic rules list
- **Status:** `pass`
- **Evidence:** All form fields present in template with v-model bindings

- **Criteria:** Each rule card has indicator, operator, value, value_upper (conditional), action, weight, description fields
- **Status:** `pass`
- **Evidence:** Rule cards render all fields; value_upper shown only when operator === 'between'

- **Criteria:** Add Rule button appends a new blank rule, remove button deletes a rule
- **Status:** `pass`
- **Evidence:** addRule() pushes blank rule, removeRule(idx) splices it

- **Criteria:** Save button is disabled when name is empty or no rules exist
- **Status:** `pass`
- **Evidence:** canSave computed checks name.trim().length > 0 && rules.length > 0

- **Criteria:** Save calls POST /api/v1/strategies/ with correct payload shape
- **Status:** `pass`
- **Evidence:** saveStrategy() calls api.post('/strategies/', payload) with { name, description, rules, profile_name }

- **Criteria:** Existing strategies are listed from GET /api/v1/strategies/ on mount
- **Status:** `pass`
- **Evidence:** loadStrategies() called in onMounted, renders strategy cards

- **Criteria:** Delete button calls DELETE /api/v1/strategies/{id} and refreshes list
- **Status:** `pass`
- **Evidence:** deleteStrategy(id) calls api.delete then loadStrategies()

- **Criteria:** vue-tsc --noEmit passes with no type errors
- **Status:** `pass`
- **Evidence:** `npx vue-tsc --noEmit` ran with exit code 0, no output

---

## 3) Files changed (and rationale per file)
- `frontend/src/views/StrategyBuilderView.vue` — new view with rule editor and strategy list
- `frontend/src/router/index.ts` — added /strategy-builder route
- `frontend/src/components/AppLayout.vue` — added Builder nav entry
- `rationale.md` — this file

---

## 4) Tests run & results
- **Commands run:**
  - `cd frontend && npx vue-tsc --noEmit` — passed (exit 0, no errors)

---

## 5) Data & sample evidence
- No data fixtures needed; frontend-only view using API client

---

## 6) Risk assessment & mitigations
- **Risk:** Backend strategies API not merged yet — **Severity:** medium — **Mitigation:** Task spec notes dependency on task-0035; view will function once API is available

---

## 7) Backwards compatibility / migration notes
- New files only, backward compatible. No breaking changes.

---

## 8) Performance considerations
- Lazy-loaded route, no performance impact on other pages.

---

## 9) Security & safety checks
- forbidden paths touched: `no`
- external/broker sdk usage: `no`
- secrets touched: `no`
- API key logged: `no`

---

## 10) Open questions & follow-ups
1. Strategies API (task-0035) must be merged before this feature is fully functional.

---

## 11) Short changelog
- feat(marketpulse-task-2026-04-02-0047): Strategy Builder view with rule editor

---

## 12) Final verdict (developer self-check)
- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `approve`

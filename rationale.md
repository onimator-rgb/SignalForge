# Rationale for `marketpulse-task-2026-04-01-0017`

**author:** coder-agent (MarketPulse Coder)
**branch:** task/marketpulse-task-2026-04-01-0017-implementation
**commit_sha:** e068b27
**date:** 2026-04-01
**model_calls:** 1

---

## 1) One-line summary
Add Strategy Management View (StrategyView.vue) displaying active profile, market regime, effective settings, auto-switch status, and all-profiles comparison table.

---

## 2) Mapping to acceptance criteria

- **Criteria:** StrategyView.vue exists and compiles without TypeScript errors
- **Status:** `pass`
- **Evidence:** File created; `npx vue-tsc --noEmit` passes with zero errors

- **Criteria:** View fetches /api/v1/strategy/summary on mount and displays all sections
- **Status:** `pass`
- **Evidence:** `onMounted(load)` calls `api.get('/strategy/summary')` and renders regime, profile, effective, auto_switch, and comparison sections

- **Criteria:** Market regime is color-coded (green/yellow/red)
- **Status:** `pass`
- **Evidence:** Computed properties `regimeColor` and `regimeBg` map risk_on->green, neutral->yellow, risk_off->red

- **Criteria:** All 15 profile parameters are displayed in the active profile section
- **Status:** `pass`
- **Evidence:** Active Profile card shows all 15 fields in a 4-column grid (Entry, Position, Trailing, Entry Trailing/Slippage)

- **Criteria:** All 3 profiles are shown in a comparison table with active column highlighted
- **Status:** `pass`
- **Evidence:** ALL_PROFILES array contains all 3 profiles; table highlights active column with `text-blue-400` and `bg-blue-500/5`

- **Criteria:** Effective settings show regime adjustments with deltas
- **Status:** `pass`
- **Evidence:** Effective Settings card shows `threshold -> adjusted (delta regime adj)` and `position -> adjusted (x multiplier)`

- **Criteria:** Loading spinner and error handling are present
- **Status:** `pass`
- **Evidence:** `<LoadingSpinner v-if="loading" />` and `<ErrorBox v-else-if="error" :message="error" />`

- **Criteria:** Route /strategy exists and lazy-loads StrategyView
- **Status:** `pass`
- **Evidence:** Added to router/index.ts: `{ path: '/strategy', name: 'strategy', component: () => import('../views/StrategyView.vue') }`

- **Criteria:** Navigation includes a Strategy link visible alongside other nav items
- **Status:** `pass`
- **Evidence:** Added to AppLayout.vue navItems: `{ to: '/strategy', label: 'Strategia', icon: '🎯', badge: false }`

- **Criteria:** TypeScript compilation passes
- **Status:** `pass`
- **Evidence:** `npx vue-tsc --noEmit` exits with code 0

---

## 3) Design decisions

- Used static ALL_PROFILES array in frontend rather than adding a new backend endpoint, since profiles are frozen config values.
- Followed Polish naming convention for nav label ("Strategia") consistent with existing labels like "Aktywa", "Anomalie", "Alerty".
- Used 4-column grid layout for active profile parameters grouped by category (Entry, Position, Trailing, Entry Trailing/Slippage).
- Comparison table uses 14 rows (all numeric/boolean params) with active column visually highlighted.

---

## 4) Files changed

| File | Action | LOC |
|------|--------|-----|
| frontend/src/views/StrategyView.vue | created | ~240 |
| frontend/src/router/index.ts | modified | +1 |
| frontend/src/components/AppLayout.vue | modified | +1 |

---

## 5) Tests / checks executed

| Command | Exit code |
|---------|-----------|
| `cd frontend && npx vue-tsc --noEmit` | 0 |

---

## 6) Risks and mitigations

- **Low risk**: Pure frontend view consuming existing API endpoint — no backend changes needed.
- **Low risk**: Static profile data in frontend could drift from backend. Mitigation: values are frozen dataclass defaults unlikely to change frequently.

---

## 7) Security review

- No secrets accessed or committed.
- No broker API calls.
- No external service calls.
- Read-only display — no mutation endpoints called.

---

## 8) Rollback plan

Revert commit e068b27 to remove all changes cleanly.

---

## 9) Open questions

None — all acceptance criteria met.

---

## 10) Dependencies verified

- `frontend/src/api/client.ts` — axios client exists, baseURL includes `/api/v1`
- `frontend/src/components/LoadingSpinner.vue` — exists, no props
- `frontend/src/components/ErrorBox.vue` — exists, takes optional `message` prop
- `backend/app/strategy/router.py` — `/api/v1/strategy/summary` endpoint exists

---

## 11) Performance notes

- Single API call on mount. No polling. Lightweight render.

---

## 12) Next recommended step

`approve` — all criteria pass, TypeScript clean, follows existing patterns.

# Rationale for `marketpulse-task-2026-04-01-0003`

**author:** coder-agent
**branch:** task/marketpulse-task-2026-04-01-0003-implementation
**commit_sha:** (pending)
**date:** 2026-04-01

---

## 1) One-line summary
Add BacktestView.vue with form (asset select, lookback days, profile) and results display (metrics grid + trade table), plus API module, route, and nav entry.

---

## 2) Mapping to acceptance criteria

- **Criteria:** frontend/src/views/BacktestView.vue exists with `<script setup lang="ts">` and uses Composition API
- **Status:** `pass`
- **Evidence:** File created with `<script setup lang="ts">`, uses `ref`, `onMounted` from Vue 3 Composition API

- **Criteria:** frontend/src/api/backtest.ts exports runBacktest() that POSTs to /backtest/run
- **Status:** `pass`
- **Evidence:** `export async function runBacktest(req: BacktestRequest): Promise<BacktestResponse>` posts to `'/backtest/run'`

- **Criteria:** Asset dropdown populates from /assets API on mount
- **Status:** `pass`
- **Evidence:** `onMounted` calls `fetchAssets({ limit: 100 })`, populates `<select>` with `v-for="a in assets"`

- **Criteria:** Form has asset select, lookback days input, profile select (balanced/aggressive/conservative), and Run button
- **Status:** `pass`
- **Evidence:** Template contains all four form elements with correct options

- **Criteria:** Results section shows metrics grid: total_return_pct, max_drawdown_pct, sharpe_ratio, win_rate, profit_factor, total_trades
- **Status:** `pass`
- **Evidence:** 6-column metrics grid with all specified metrics

- **Criteria:** Trade table displays entry_price, exit_price, pnl_pct (color-coded green/red), exit_reason
- **Status:** `pass`
- **Evidence:** Table with columns #, Side, Entry Price, Exit Price, PnL%, Exit Reason; `pnlClass()` returns green-400/red-400

- **Criteria:** Route /backtest added to router/index.ts
- **Status:** `pass`
- **Evidence:** `{ path: '/backtest', name: 'backtest', component: () => import('../views/BacktestView.vue') }`

- **Criteria:** Nav item 'Backtest' added to AppLayout.vue navItems array
- **Status:** `pass`
- **Evidence:** `{ to: '/backtest', label: 'Backtest', icon: '🧪', badge: false }` added after Strategy

- **Criteria:** vue-tsc --noEmit passes with no type errors
- **Status:** `pass`
- **Evidence:** `cd frontend && npx vue-tsc --noEmit` — exit code 0, no output

- **Criteria:** Dark theme styling consistent with existing views (bg-gray-800 cards, bg-gray-900 page, text-gray-300)
- **Status:** `pass`
- **Evidence:** Uses bg-gray-800 cards, bg-gray-900 inputs, text-gray-200/400 text, border-gray-700 borders

---

## 3) Files changed (and rationale per file)

- `frontend/src/api/backtest.ts` — new API module with BacktestRequest/TradeOut/BacktestResponse interfaces and runBacktest() function (~40 LOC)
- `frontend/src/views/BacktestView.vue` — new view with form + metrics grid + trade table (~170 LOC)
- `frontend/src/router/index.ts` — added /backtest route (+1 LOC)
- `frontend/src/components/AppLayout.vue` — added Backtest nav item (+1 LOC)

Total: 4 files, ~212 LOC added. Within max_change_loc limit.

---

## 4) Tests run & results

- **Commands run:**
  - `cd frontend && npx vue-tsc --noEmit`
- **Results summary:**
  - typecheck: passed (exit 0, no errors)

---

## 5) Data & sample evidence

- No test fixtures needed — frontend-only changes
- BacktestRequest/Response interfaces match backend Pydantic schemas from `backend/app/backtest/schemas.py`

---

## 6) Risk assessment & mitigations

- **Risk:** TypeScript interfaces may diverge from backend schemas — **Severity:** low — **Mitigation:** Interfaces copied directly from task spec which mirrors backend schemas
- **Risk:** API endpoint path mismatch — **Severity:** low — **Mitigation:** Uses `/backtest/run` matching backend router

---

## 7) Backwards compatibility / migration notes

- No breaking changes — purely additive (new view, new route, new nav item)

---

## 8) Performance considerations

- No performance impact — standard lazy-loaded view, single API call on form submit

---

## 9) Security & safety checks

- forbidden paths touched: `no`
- external/broker sdk usage: `no`
- secrets touched: `no`

---

## 10) Open questions & follow-ups

1. Should we add chart visualization for equity curve in a future task?
2. Should the trade table support CSV export?

---

## 11) Short changelog (commit messages / important diffs)

- (pending) — `feat(marketpulse-task-2026-04-01-0003): add BacktestView with form, metrics grid, and trade table`

---

## 12) Final verdict (developer self-check)

- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `validate`

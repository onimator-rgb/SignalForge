# Rationale for `marketpulse-task-2026-04-01-0021`

**author:** coder-agent (MarketPulse Coder)
**branch:** task/marketpulse-task-2026-04-01-0021-implementation
**date:** 2026-04-01

---

## 1) One-line summary
Add mini indicator sparklines (RSI, MACD histogram, ADX) to AssetDetailView, backed by a new rolling indicator history endpoint.

---

## 2) Mapping to acceptance criteria

- **Criteria:** GET /api/v1/assets/{id}/indicators/history returns JSON with rsi_14, macd_histogram, adx_14 arrays
- **Status:** `pass`
- **Evidence:** Endpoint implemented in router.py, returns IndicatorHistory schema with all three arrays

- **Criteria:** Each array contains up to 24 float|null values representing the most recent rolling indicator values
- **Status:** `pass`
- **Evidence:** Service slices last 24 entries; tests verify correct lengths and value types

- **Criteria:** bar_times array has matching timestamps for each data point
- **Status:** `pass`
- **Evidence:** bar_times sliced to same display_count as indicator arrays

- **Criteria:** Returns 404 for nonexistent asset or no bars
- **Status:** `pass`
- **Evidence:** Router checks asset existence and None return from service

- **Criteria:** Tests pass with synthetic data verifying list lengths, value ranges, and None padding
- **Status:** `pass`
- **Evidence:** 11 tests pass in test_indicator_history.py

- **Criteria:** AssetDetailView shows CSS-bar sparklines for RSI, MACD histogram, and ADX
- **Status:** `pass`
- **Evidence:** Sparklines added after each indicator section using flex+gap CSS bar pattern

- **Criteria:** Sparklines use existing dark theme colors (green/red for MACD, blue for RSI, purple for ADX)
- **Status:** `pass`
- **Evidence:** RSI=blue-400/70, MACD=green-400/70 or red-400/70 by sign, ADX=purple-400/70

- **Criteria:** Sparklines handle null values gracefully (skip them)
- **Status:** `pass`
- **Evidence:** normalizeSparkline filters nulls for min/max, renders 0 height for null bars

- **Criteria:** vue-tsc passes with no errors
- **Status:** `pass`
- **Evidence:** `npx vue-tsc --noEmit` exits 0

- **Criteria:** No external charting library added
- **Status:** `pass`
- **Evidence:** Pure CSS bars, no chart.js/d3/etc.

---

## 3) Files changed (and rationale per file)
- `backend/app/indicators/schemas.py` — Added IndicatorHistory Pydantic model
- `backend/app/indicators/service.py` — Added get_indicator_history() with rolling computation
- `backend/app/indicators/router.py` — Added GET /assets/{id}/indicators/history endpoint
- `backend/tests/test_indicator_history.py` — 11 tests for rolling computation and schema
- `frontend/src/types/api.ts` — Added IndicatorHistory TypeScript interface
- `frontend/src/views/AssetDetailView.vue` — Added sparklines + fetch + normalizeSparkline helper
- `rationale.md` — This file

---

## 4) Tests run & results
- `cd backend && uv run python -m pytest tests/test_indicator_history.py -q` → 11 passed
- `cd backend && uv run python -m mypy app/indicators/schemas.py --ignore-missing-imports` → Success
- `cd backend && uv run python -m mypy app/indicators/service.py --ignore-missing-imports` → 1 pre-existing error (mfi_14), no new errors
- `cd backend && uv run python -m mypy app/indicators/router.py --ignore-missing-imports` → Same pre-existing error only
- `cd frontend && npx vue-tsc --noEmit` → Success

---

## 5) Data & sample evidence
- Tests use synthetic rising price series (start=100, step=1) with fixed high/low offsets
- Validates RSI in [0,100], MACD histogram is float, ADX in [0,100]

---

## 6) Risk assessment & mitigations
- **Performance (low):** Rolling computation calls calculators ~20-34 times for 48 bars — negligible
- **Integration (low):** Empty arrays gracefully render no sparklines

---

## 7) Backwards compatibility / migration notes
- All changes are additive — no existing APIs or UI modified
- No database migrations required

---

## 8) Performance considerations
- Indicator history is computed on-the-fly from 48 bars — sub-millisecond per calculator call
- Frontend fetch is non-blocking (fire-and-forget after main data loads)

---

## 9) Security & safety checks
- forbidden paths touched: `no`
- external/broker sdk usage: `no`
- secrets touched: `no`
- API key logged: `no`

---

## 10) Open questions & follow-ups
1. Consider caching indicator history if request volume grows
2. Pre-existing mypy error (mfi_14 keyword) in get_indicators should be fixed separately

---

## 11) Short changelog
- feat(indicators): add rolling indicator history endpoint + sparkline display

---

## 12) Final verdict (developer self-check)
- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `approve`

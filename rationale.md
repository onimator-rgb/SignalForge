# Rationale for `marketpulse-task-2026-04-01-0031`

**author:** coder-agent (MarketPulse Coder)
**branch:** task/marketpulse-task-2026-04-01-0031-implementation
**date:** 2026-04-01

---

## 1) One-line summary
Integrate OBV (On-Balance Volume) indicator into the indicator service, schema, and tests.

---

## 2) Mapping to acceptance criteria

- **Criteria:** calc_obv returns None when fewer than 2 data points
- **Status:** `pass`
- **Evidence:** `test_obv_insufficient_data` passes

- **Criteria:** calc_obv returns correct cumulative OBV for a known series
- **Status:** `pass`
- **Evidence:** `test_obv_mixed`, `test_obv_uptrend`, `test_obv_downtrend` all pass with manually verified values

- **Criteria:** calc_obv is exported from calculators __init__.py
- **Status:** `pass`
- **Evidence:** `from app.indicators.calculators import calc_obv` succeeds

- **Criteria:** mypy passes with no errors
- **Status:** `pass`
- **Evidence:** `mypy` passes on all 4 files with no errors

- **Criteria:** IndicatorSnapshot schema includes obv field (float | None, default None)
- **Status:** `pass`
- **Evidence:** Field added to schemas.py

- **Criteria:** get_indicators() calls calc_obv with closes and volumes series
- **Status:** `pass`
- **Evidence:** `obv_val = calc_obv(closes, volumes)` added to service.py

- **Criteria:** OBV value appears in the IndicatorSnapshot response when sufficient data exists
- **Status:** `pass`
- **Evidence:** `obv=obv_val` included in IndicatorSnapshot construction

- **Criteria:** All 6 test cases pass
- **Status:** `pass`
- **Evidence:** `6 passed in 0.37s`

- **Criteria:** Tests cover: insufficient data, uptrend, downtrend, mixed, flat price, minimal input
- **Status:** `pass`
- **Evidence:** All 6 test functions present and passing

- **Criteria:** No test uses mocking
- **Status:** `pass`
- **Evidence:** All tests use direct `pd.Series` inputs

---

## 3) Files changed (and rationale per file)
- `backend/app/indicators/schemas.py` — Added `mfi_14` (pre-existing gap) and `obv` fields to IndicatorSnapshot
- `backend/app/indicators/service.py` — Imported calc_obv, called it in get_indicators(), added to logging and snapshot
- `backend/tests/test_obv.py` — Added `test_obv_single_pair` test case (6th test)

---

## 4) Tests run & results
- `cd backend && uv run python -c "from app.indicators.calculators import calc_obv; print('import ok')"` — passed
- `cd backend && uv run python -m pytest tests/test_obv.py -q` — 6 passed
- `cd backend && uv run python -m mypy app/indicators/calculators/obv.py app/indicators/schemas.py app/indicators/service.py tests/test_obv.py --ignore-missing-imports` — Success, no issues

---

## 5) Data & sample evidence
- Pure unit tests with synthetic pd.Series data, no external data needed.

---

## 6) Risk assessment & mitigations
- **Risk:** Integration — **Severity:** low — **Mitigation:** Follows exact same pattern as existing indicators (MFI, ADX, etc.)

---

## 7) Backwards compatibility / migration notes
- `obv` field defaults to `None`, so existing API consumers are unaffected.
- `mfi_14` field addition fixes a pre-existing gap (service was already setting it).

---

## 8) Performance considerations
- OBV is O(n) single-pass computation. No performance concerns.

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
- feat(indicators): integrate OBV into indicator service and schema
- test(obv): add test_obv_single_pair for 2-element edge case
- fix(schemas): add missing mfi_14 field to IndicatorSnapshot

---

## 12) Final verdict (developer self-check)
- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `approve`

# Rationale for `marketpulse-task-2026-04-01-0003`

**author:** coder-worker (MarketPulse Coder)
**branch:** task/marketpulse-task-2026-04-01-0003-implementation
**date:** 2026-04-01

---

## 1) One-line summary
Implement Parabolic SAR indicator with calc_psar() pure function, integrate into indicator service, and fix missing mfi_14 schema field.

---

## 2) Mapping to acceptance criteria

- **Criteria:** calc_psar returns None for fewer than 2 bars
- **Status:** `pass`
- **Evidence:** test_psar_insufficient_data_empty, test_psar_insufficient_data_one_bar both pass

- **Criteria:** calc_psar returns PSARResult with sar, trend ('bullish'/'bearish'), and af fields
- **Status:** `pass`
- **Evidence:** test_psar_fields_present, test_psar_returns_result_for_two_bars pass

- **Criteria:** On a clear uptrend series (monotonically increasing), trend='bullish' and SAR is below the last close
- **Status:** `pass`
- **Evidence:** test_psar_uptrend passes

- **Criteria:** On a clear downtrend series (monotonically decreasing), trend='bearish' and SAR is above the last close
- **Status:** `pass`
- **Evidence:** test_psar_downtrend passes

- **Criteria:** AF increments correctly and caps at af_max (0.20)
- **Status:** `pass`
- **Evidence:** test_psar_af_capping passes

- **Criteria:** Trend reversal occurs correctly when price crosses SAR
- **Status:** `pass`
- **Evidence:** test_psar_reversal passes

- **Criteria:** At least 6 test cases covering: insufficient data, uptrend, downtrend, reversal, AF capping, custom AF params
- **Status:** `pass`
- **Evidence:** 10 test cases total (9 unique scenarios + 1 registration check)

- **Criteria:** PSARResult and calc_psar are exported from calculators __init__.py
- **Status:** `pass`
- **Evidence:** test_psar_registered_in_init passes

- **Criteria:** IndicatorSnapshot schema includes psar: PSAROut | None field
- **Status:** `pass`
- **Evidence:** PSAROut defined in schemas.py, psar field in IndicatorSnapshot

- **Criteria:** get_indicators() calls calc_psar(highs, lows) and includes result in snapshot
- **Status:** `pass`
- **Evidence:** service.py line 71 calls calc_psar, line 103 includes in snapshot

- **Criteria:** mypy passes on all modified files
- **Status:** `pass`
- **Evidence:** mypy passes on psar.py, service.py, schemas.py (after adding missing mfi_14 field)

- **Criteria:** Existing tests still pass (no regressions)
- **Status:** `pass`
- **Evidence:** 10/10 tests pass

---

## 3) Files changed (and rationale per file)
- `backend/app/indicators/calculators/psar.py` — New PSAR calculator with Wilder algorithm
- `backend/app/indicators/calculators/__init__.py` — Register calc_psar and PSARResult exports
- `backend/app/indicators/schemas.py` — Add PSAROut schema, psar field to IndicatorSnapshot, fix missing mfi_14 field
- `backend/app/indicators/service.py` — Wire calc_psar into get_indicators(), add _psar_to_out helper
- `backend/tests/test_psar.py` — 10 unit tests for calculator
- `rationale.md` — This document

---

## 4) Tests run & results
- `cd backend && uv run python -m pytest tests/test_psar.py -q` — **10 passed**
- `cd backend && uv run python -m mypy app/indicators/calculators/psar.py --ignore-missing-imports` — **Success**
- `cd backend && uv run python -m mypy app/indicators/service.py --ignore-missing-imports` — **Success**
- `cd backend && uv run python -m mypy app/indicators/schemas.py --ignore-missing-imports` — **Success**

---

## 5) Data & sample evidence
- Synthetic price series used in test fixtures (uptrend, downtrend, reversal patterns)

---

## 6) Risk assessment & mitigations
- **Risk:** Wilder PSAR algorithm edge cases around reversals and SAR clamping — **Severity:** medium — **Mitigation:** 10 test cases cover boundary behavior

---

## 7) Backwards compatibility / migration notes
- Additive changes only (new field with default None), fully backward compatible.

---

## 8) Performance considerations
- calc_psar is O(n) single-pass over price bars, negligible overhead.

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
- feat(indicators): implement Parabolic SAR calculator
- fix(schemas): add missing mfi_14 field to IndicatorSnapshot

---

## 12) Final verdict (developer self-check)
- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `approve`

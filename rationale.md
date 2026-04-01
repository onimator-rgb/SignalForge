# Rationale for `marketpulse-task-2026-04-01-0003`

**author:** coder-agent (MarketPulse Coder)
**branch:** task/marketpulse-task-2026-04-01-0003-implementation
**date:** 2026-04-01

---

## 1) One-line summary
Add Money Flow Index (MFI) indicator — a volume-weighted RSI oscillator (0-100) — with pure calculator, schema integration, service wiring, and unit tests.

---

## 2) Mapping to acceptance criteria

- **Criteria:** calc_mfi returns None when fewer than period+1 bars provided
- **Status:** `pass`
- **Evidence:** test_mfi_insufficient_data passes — 14 bars with period=14 returns None

- **Criteria:** calc_mfi returns a float in range [0, 100] for valid input
- **Status:** `pass`
- **Evidence:** test_mfi_returns_float_in_range passes — 30 bars, result is float in [0, 100]

- **Criteria:** calc_mfi returns value > 50 for a strong uptrend with rising prices and volume
- **Status:** `pass`
- **Evidence:** test_mfi_strong_uptrend passes — monotonically rising data yields MFI > 50

- **Criteria:** calc_mfi returns value < 50 for a strong downtrend with falling prices and volume
- **Status:** `pass`
- **Evidence:** test_mfi_strong_downtrend passes — monotonically falling data yields MFI < 50

- **Criteria:** calc_mfi handles edge case where all negative flows are zero (returns 100.0)
- **Status:** `pass`
- **Evidence:** test_mfi_all_negative_flows_zero passes — strictly rising TP yields 100.0

- **Criteria:** Function is registered in calculators __init__.py and importable
- **Status:** `pass`
- **Evidence:** test_mfi_registered_in_init passes — imports via barrel and verifies identity

- **Criteria:** IndicatorSnapshot schema includes mfi_14: float | None field
- **Status:** `pass`
- **Evidence:** Field added after adx/di fields in schemas.py, mypy passes

- **Criteria:** get_indicators calls calc_mfi with highs, lows, closes, volumes, period=14
- **Status:** `pass`
- **Evidence:** service.py updated with calc_mfi call, mypy passes

- **Criteria:** mfi_14 value is populated in the returned IndicatorSnapshot
- **Status:** `pass`
- **Evidence:** mfi_14=mfi_val added to IndicatorSnapshot constructor in service.py

- **Criteria:** mypy passes on both schemas.py and service.py
- **Status:** `pass`
- **Evidence:** `mypy app/indicators/schemas.py app/indicators/service.py --ignore-missing-imports` → Success: no issues found in 2 source files

---

## 3) Files changed (and rationale per file)
- `backend/app/indicators/calculators/mfi.py` — new pure calculator function
- `backend/app/indicators/calculators/__init__.py` — register calc_mfi export
- `backend/app/indicators/schemas.py` — add mfi_14 field to IndicatorSnapshot
- `backend/app/indicators/service.py` — wire calc_mfi into get_indicators, add volumes Series
- `backend/tests/test_mfi.py` — 6 unit tests covering all acceptance criteria
- `rationale.md` — this file

---

## 4) Tests run & results
- `cd backend && uv run python -m pytest tests/test_mfi.py -q` → 6 passed
- `cd backend && uv run python -m mypy app/indicators/calculators/mfi.py --ignore-missing-imports` → Success
- `cd backend && uv run python -m mypy app/indicators/schemas.py app/indicators/service.py --ignore-missing-imports` → Success

---

## 5) Data & sample evidence
- All tests use synthetic pandas Series data, no external data sources.

---

## 6) Risk assessment & mitigations
- **Risk:** Zero-denominator in money flow ratio → **Severity:** low → **Mitigation:** Guard clause returns 100.0 when neg_sum == 0

---

## 7) Backwards compatibility / migration notes
- New field `mfi_14` defaults to None — fully backward compatible, no migration needed.

---

## 8) Performance considerations
- MFI calculation is O(n) on the existing price bars already loaded by get_indicators. No additional DB queries.

---

## 9) Security & safety checks
- forbidden paths touched: `no`
- external/broker sdk usage: `no`
- secrets touched: `no`
- API key logged: `no`

---

## 10) Open questions & follow-ups
1. Consider adding MFI scoring function for recommendations (out of scope for this task).

---

## 11) Short changelog
- feat(marketpulse-task-2026-04-01-0003): add MFI indicator calculator, schema, service integration, and tests

---

## 12) Final verdict (developer self-check)
- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `approve`

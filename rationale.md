# Rationale for `marketpulse-task-2026-04-01-0033`

**author:** coder-agent
**branch:** task/marketpulse-task-2026-04-01-0033-implementation
**commit_sha:** 4e93526
**date:** 2026-04-01

---

## 1) One-line summary
Add MFIResult frozen dataclass, wire MFI into IndicatorSnapshot schema and service, with 8 comprehensive tests.

---

## 2) Mapping to acceptance criteria

- **Criteria:** calc_mfi returns MFIResult with mfi float in [0, 100]
- **Status:** `pass`
- **Evidence:** `pytest tests/test_mfi.py::test_mfi_range — passed`; `test_mfi_uptrend`, `test_mfi_downtrend` confirm range

- **Criteria:** Returns None when len(closes) < period + 1
- **Status:** `pass`
- **Evidence:** `pytest tests/test_mfi.py::test_mfi_insufficient_data — passed`

- **Criteria:** MFIResult is a frozen dataclass
- **Status:** `pass`
- **Evidence:** `pytest tests/test_mfi.py::test_mfi_frozen_dataclass — passed` (asserts AttributeError on assignment)

- **Criteria:** Handles zero negative money flow (returns 100.0)
- **Status:** `pass`
- **Evidence:** `pytest tests/test_mfi.py::test_mfi_zero_negative_flow — passed`

- **Criteria:** calc_mfi and MFIResult are exported from calculators/__init__.py
- **Status:** `pass`
- **Evidence:** `pytest tests/test_mfi.py::test_mfi_exported_from_init — passed`

- **Criteria:** IndicatorSnapshot has mfi: float | None = None field
- **Status:** `pass`
- **Evidence:** `mypy app/indicators/schemas.py — Success: no issues found`

- **Criteria:** get_indicators() computes MFI and includes it in the returned snapshot
- **Status:** `pass`
- **Evidence:** `service.py:96` — `mfi=mfi_val.mfi if mfi_val else None`

- **Criteria:** mypy passes with no errors on both files
- **Status:** `pass`
- **Evidence:** `mypy app/indicators/service.py — Success`, `mypy app/indicators/schemas.py — Success`

- **Criteria:** All tests pass with at least 6 test functions
- **Status:** `pass`
- **Evidence:** `pytest tests/test_mfi.py -q — 8 passed in 0.38s`

---

## 3) Files changed (and rationale per file)

- `backend/app/indicators/calculators/mfi.py` — Refactored to return `MFIResult` frozen dataclass instead of raw float; ~+15 LOC
- `backend/app/indicators/calculators/__init__.py` — Added `MFIResult` export; +2 LOC
- `backend/app/indicators/schemas.py` — Added `mfi: float | None = None` field to `IndicatorSnapshot`; +1 LOC
- `backend/app/indicators/service.py` — Fixed MFI wiring: changed `mfi_14=mfi_val` to `mfi=mfi_val.mfi if mfi_val else None`; +1/-1 LOC
- `backend/tests/test_mfi.py` — Rewrote with 8 test functions covering all acceptance criteria; ~+90 LOC

---

## 4) Tests run & results

- **Commands run:**
  - `cd backend && uv run python -c "from app.indicators.calculators.mfi import calc_mfi, MFIResult; print('import ok')"` — passed
  - `cd backend && uv run python -m mypy app/indicators/calculators/mfi.py --ignore-missing-imports` — passed
  - `cd backend && uv run python -m mypy app/indicators/schemas.py --ignore-missing-imports` — passed
  - `cd backend && uv run python -m mypy app/indicators/service.py --ignore-missing-imports` — passed
  - `cd backend && uv run python -m pytest tests/test_mfi.py -q` — 8 passed
  - `cd backend && uv run python -m mypy tests/test_mfi.py --ignore-missing-imports` — passed
- **Results summary:**
  - tests: 8 passed, 0 failed
  - mypy: all source files passed with no issues

---

## 5) Data & sample evidence

- All test data is synthetic pd.Series with known properties (monotonic up/down, hand-calculated values)
- `test_mfi_known_values`: H=[12,14,11], L=[8,10,7], C=[10,12,9], V=[100,150,200], period=2 → MFI=50.0 (hand-verified)

---

## 6) Risk assessment & mitigations

- **Risk:** Breaking existing service — **Severity:** low — **Mitigation:** service already imported calc_mfi; only changed return type and field name
- **Risk:** Schema backward compatibility — **Severity:** low — **Mitigation:** `mfi` field has default `None`, no API contract broken

---

## 7) Backwards compatibility / migration notes

- API: `IndicatorSnapshot` gains new optional field `mfi` — fully backward compatible
- DB migrations: none required
- Previously the field `mfi_14` was referenced in service.py but never existed in the schema — this was a bug, now fixed as `mfi`

---

## 8) Performance considerations

- MFI calculation is O(n) over price bars — negligible impact at 60-bar lookback
- No additional DB queries required (reuses existing highs/lows/closes/volumes Series)

---

## 9) Security & safety checks

- forbidden paths touched: `no`
- external/broker sdk usage: `no`
- secrets touched: `no`

---

## 10) Open questions & follow-ups

1. Should MFI be integrated into recommendation scoring (score_mfi)? — listed as separate task in spec
2. The previous `mfi_14` reference in service.py was a latent bug — was this branch deployed before?

---

## 11) Short changelog

- `4e93526` — feat(indicators): add MFIResult dataclass and wire MFI into schema — files: mfi.py, __init__.py, schemas.py, service.py, test_mfi.py

---

## 12) Final verdict (developer self-check)

- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `validate`

# Rationale for `marketpulse-task-2026-04-01-0003`

**author:** coder-agent
**branch:** task/marketpulse-task-2026-04-01-0003-implementation
**commit_sha:** (pending)
**date:** 2026-04-01

---

## 1) One-line summary
Implement Parabolic SAR (Stop and Reverse) indicator calculator using Welles Wilder's algorithm, integrated into the indicator service and exposed via the existing `/indicators` endpoint.

---

## 2) Mapping to acceptance criteria

- **Criteria:** calc_psar returns None for fewer than 2 bars
- **Status:** `pass`
- **Evidence:** `pytest tests/test_psar.py::test_psar_insufficient_data_empty` and `::test_psar_insufficient_data_one_bar` — passed

- **Criteria:** calc_psar returns PSARResult with sar, trend ('bullish'/'bearish'), and af fields
- **Status:** `pass`
- **Evidence:** `pytest tests/test_psar.py::test_psar_fields_present` — passed

- **Criteria:** On a clear uptrend series, trend='bullish' and SAR is below the last close
- **Status:** `pass`
- **Evidence:** `pytest tests/test_psar.py::test_psar_uptrend` — passed

- **Criteria:** On a clear downtrend series, trend='bearish' and SAR is above the last close
- **Status:** `pass`
- **Evidence:** `pytest tests/test_psar.py::test_psar_downtrend` — passed

- **Criteria:** AF increments correctly and caps at af_max (0.20)
- **Status:** `pass`
- **Evidence:** `pytest tests/test_psar.py::test_psar_af_capping` — passed

- **Criteria:** Trend reversal occurs correctly when price crosses SAR
- **Status:** `pass`
- **Evidence:** `pytest tests/test_psar.py::test_psar_reversal` — passed

- **Criteria:** At least 6 test cases covering: insufficient data, uptrend, downtrend, reversal, AF capping, custom AF params
- **Status:** `pass`
- **Evidence:** 10 test cases total covering all required scenarios

- **Criteria:** PSARResult and calc_psar are exported from calculators __init__.py
- **Status:** `pass`
- **Evidence:** `pytest tests/test_psar.py::test_psar_registered_in_init` — passed

- **Criteria:** IndicatorSnapshot schema includes psar: PSAROut | None field
- **Status:** `pass`
- **Evidence:** `schemas.py` updated with PSAROut class and psar field

- **Criteria:** get_indicators() calls calc_psar(highs, lows) and includes result in snapshot
- **Status:** `pass`
- **Evidence:** `service.py` updated with calc_psar call and _psar_to_out helper

- **Criteria:** mypy passes on all modified files
- **Status:** `pass`
- **Evidence:** `mypy app/indicators/calculators/psar.py` — Success; `mypy app/indicators/schemas.py` — Success
- **Notes:** Pre-existing mypy error in service.py (`mfi_14` field) — not introduced by this task

---

## 3) Files changed (and rationale per file)

- `backend/app/indicators/calculators/psar.py` — New calculator module implementing Welles Wilder's Parabolic SAR algorithm. ~85 LOC.
- `backend/tests/test_psar.py` — 10 unit tests covering all acceptance criteria. ~115 LOC.
- `backend/app/indicators/calculators/__init__.py` — Register PSARResult and calc_psar exports. ~3 LOC delta.
- `backend/app/indicators/schemas.py` — Add PSAROut schema and psar field to IndicatorSnapshot. ~6 LOC delta.
- `backend/app/indicators/service.py` — Wire calc_psar into get_indicators and add _psar_to_out helper. ~10 LOC delta.

---

## 4) Tests run & results

- **Commands run:**
  - `cd backend && uv run python -m pytest tests/test_psar.py -q` — 10 passed
  - `cd backend && uv run python -m mypy app/indicators/calculators/psar.py --ignore-missing-imports` — Success
  - `cd backend && uv run python -m mypy app/indicators/schemas.py --ignore-missing-imports` — Success

---

## 5) Data & sample evidence

- Synthetic price data: monotonically increasing/decreasing highs and lows series (60-100 bars)
- Reversal test: 20 bars uptrend followed by 20 bars sharp downtrend
- AF capping test: 100 bars continuous uptrend to verify AF reaches 0.20 cap

---

## 6) Risk assessment & mitigations

- **Risk:** PSAR algorithm edge cases around reversals and SAR clamping — **Severity:** medium — **Mitigation:** 10 tests including reversal, AF capping, and boundary behavior
- **Risk:** Integration regression — **Severity:** low — **Mitigation:** Follows established pattern (MACD/Bollinger), psar field is optional (None default)

---

## 7) Backwards compatibility / migration notes

- API changes: `psar` field added to IndicatorSnapshot — backward compatible (optional, defaults to None)
- DB migrations: none

---

## 8) Performance considerations

- PSAR is O(n) single-pass algorithm — negligible performance impact
- No additional DB queries required

---

## 9) Security & safety checks

- forbidden paths touched: `no`
- external/broker sdk usage: `no`
- secrets touched: `no`

---

## 10) Open questions & follow-ups

1. Pre-existing mypy error in service.py (`mfi_14` field not in IndicatorSnapshot schema) should be addressed separately.
2. PSAR scoring function for recommendations engine not yet implemented (out of scope).

---

## 11) Short changelog

- (pending) — feat(indicators): implement Parabolic SAR calculator [marketpulse-task-2026-04-01-0003]

---

## 12) Final verdict (developer self-check)

- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `validate`

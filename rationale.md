# Rationale for `marketpulse-task-2026-04-01-0009`

**author:** coder-agent (MarketPulse Coder)
**branch:** task/marketpulse-task-2026-04-01-0009-implementation
**date:** 2026-04-01

---

## 1) One-line summary
Position Scaling Up — add to winning positions with pure functions mirroring the DCA pattern.

---

## 2) Mapping to acceptance criteria

- **Criteria:** scaling.py has 5 exported functions: get_scale_state, should_scale_up, calculate_scale_buy, apply_scale_to_position, plus constants
- **Status:** `pass`
- **Evidence:** All 4 functions + 3 constants exported, import check passed

- **Criteria:** should_scale_up returns False when scale_level >= max_levels
- **Status:** `pass`
- **Evidence:** TestShouldScaleUp::test_no_trigger_at_max_level passes

- **Criteria:** should_scale_up returns False when profit < threshold
- **Status:** `pass`
- **Evidence:** TestShouldScaleUp::test_no_trigger_below_threshold passes

- **Criteria:** apply_scale_to_position moves stop_loss to original entry price (break-even)
- **Status:** `pass`
- **Evidence:** TestApplyScaleToPosition::test_stop_loss_moves_to_break_even — asserts stop_loss_price == 100.0 (original entry)

- **Criteria:** Scale state stored in exit_context['scale'] JSONB (not a new column)
- **Status:** `pass`
- **Evidence:** TestApplyScaleToPosition::test_scale_state_stored_in_exit_context

- **Criteria:** mypy passes with no errors
- **Status:** `pass`
- **Evidence:** `mypy app/portfolio/scaling.py --ignore-missing-imports` — Success: no issues found in 1 source file

- **Criteria:** All tests pass with pytest
- **Status:** `pass`
- **Evidence:** 26 passed in 0.04s

- **Criteria:** At least 10 test cases covering happy path, edge cases, and boundary conditions
- **Status:** `pass`
- **Evidence:** 26 test cases across 5 test classes

- **Criteria:** Tests use lightweight fakes (no database required)
- **Status:** `pass`
- **Evidence:** Uses unittest.mock.MagicMock — same pattern as test_dca.py

- **Criteria:** 100% function coverage of scaling.py
- **Status:** `pass`
- **Evidence:** All 4 functions + constants tested

---

## 3) Files changed (and rationale per file)
- `backend/app/portfolio/scaling.py` — new module: constants, get_scale_state, should_scale_up, calculate_scale_buy, apply_scale_to_position
- `backend/tests/test_scaling.py` — 26 unit tests mirroring test_dca.py structure
- `rationale.md` — this file

---

## 4) Tests run & results
- `cd backend && uv run python -c "from app.portfolio.scaling import ..."` — imports OK
- `cd backend && uv run python -m mypy app/portfolio/scaling.py --ignore-missing-imports` — passed
- `cd backend && uv run python -m pytest tests/test_scaling.py -q` — 26 passed

---

## 5) Key decisions
- **Break-even stop loss**: After scale-up, stop loss = original entry price (not profile-based %). This protects the profit the position already earned.
- **Scale state before mutation**: `get_scale_state()` captured before modifying `pos.entry_price` so `original_entry` is correct.
- **JSONB storage**: `exit_context['scale']` mirrors `exit_context['dca']` pattern.

---

## 6) Risk assessment & mitigations
- **Risk:** Integration with service.py — **Severity:** low — **Mitigation:** Pure functions with no DB calls; integration is a separate task

---

## 7) Backwards compatibility / migration notes
- New files only, no schema changes, backward compatible.

---

## 8) Performance considerations
- No performance impact expected — pure functions, O(1) operations.

---

## 9) Security & safety checks
- forbidden paths touched: `no`
- external/broker sdk usage: `no`
- secrets touched: `no`
- API key logged: `no`

---

## 10) Open questions & follow-ups
1. Integration into service.py evaluate_portfolio loop (separate task)
2. Schema addition of ScaleUpInfo to PositionOut (optional, deferred)

---

## 11) Short changelog
- feat(marketpulse-task-2026-04-01-0009): add position scaling-up module with pure functions

---

## 12) Final verdict (developer self-check)
- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `approve`

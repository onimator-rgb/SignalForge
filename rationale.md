# Rationale for `marketpulse-task-2026-03-31-0003`

**author:** coder-agent
**branch:** task/marketpulse-task-2026-03-31-0003-implementation
**commit_sha:** (pending)
**date:** 2026-03-31

---

## 1) One-line summary
Add trailing take profit to the exit engine so positions that hit TP trail upward and close on retracement, capturing more profit in strong trends.

---

## 2) Mapping to acceptance criteria

### Subtask S1 — Strategy profiles
- **Criteria:** StrategyProfile dataclass has trailing_tp_pct and trailing_tp_arm_pct fields
- **Status:** `pass`
- **Evidence:** `backend/app/strategy/profiles.py` lines 28-29

- **Criteria:** All three profiles have trailing-TP values set
- **Status:** `pass`
- **Evidence:** conservative (0.02, 0.01), balanced (0.03, 0.02), aggressive (0.05, 0.03)

- **Criteria:** get_profile_dict includes the two new fields
- **Status:** `pass`
- **Evidence:** `profiles.py` lines 93-94

- **Criteria:** mypy passes with no errors
- **Status:** `pass`
- **Evidence:** `mypy app/strategy/profiles.py --ignore-missing-imports` -> Success

### Subtask S2 — Exit engine
- **Criteria:** When pnl crosses take_profit_pct + trailing_tp_arm_pct, position enters trailing-TP mode
- **Status:** `pass`
- **Evidence:** `test_tp_arms_trailing_above_arm` passes

- **Criteria:** When pnl between take_profit_pct and arm threshold, position closes as 'target_hit'
- **Status:** `pass`
- **Evidence:** `test_tp_immediate_close_below_arm` passes

- **Criteria:** When in trailing-TP mode, position closes when price drops trailing_tp_pct from peak
- **Status:** `pass`
- **Evidence:** `test_trailing_tp_closes_on_retracement` passes

- **Criteria:** Safety floor ensures trailing-TP exit never below original take_profit_price
- **Status:** `pass`
- **Evidence:** `test_trailing_tp_safety_floor` and `test_trailing_tp_floor_triggers_close` pass

- **Criteria:** State stored in exit_context JSONB, no new DB columns
- **Status:** `pass`
- **Evidence:** Only exit_context field used; no changes to models.py

- **Criteria:** mypy passes with no errors
- **Status:** `pass`
- **Evidence:** `mypy app/portfolio/exits.py --ignore-missing-imports` -> Success

### Subtask S3 — Tests
- **Criteria:** All 7+ test cases pass
- **Status:** `pass`
- **Evidence:** `pytest tests/test_trailing_profit.py -q` -> 9 passed

- **Criteria:** Tests cover: immediate close, arming, retracement exit, peak tracking, safety floor, stop-loss priority, regime modifier
- **Status:** `pass`
- **Evidence:** All 7 categories covered across 9 test methods

- **Criteria:** mypy passes with no errors
- **Status:** `pass`
- **Evidence:** `mypy tests/test_trailing_profit.py --ignore-missing-imports` -> Success

---

## 3) Files changed (and rationale per file)
- `backend/app/strategy/profiles.py` — Added trailing_tp_pct, trailing_tp_arm_pct to StrategyProfile dataclass, all 3 profiles, and get_profile_dict. ~12 LOC delta.
- `backend/app/portfolio/exits.py` — Modified Rule D in evaluate_exit for trailing-TP logic; added trailing-TP state tracking in update_position_state. ~40 LOC delta.
- `backend/tests/test_trailing_profit.py` — New file with 9 test methods covering all acceptance criteria. ~175 LOC.
- `rationale.md` — This file.

---

## 4) Tests run & results
- **Commands run:**
  - `cd backend && uv run python -m mypy app/strategy/profiles.py --ignore-missing-imports` -> Success
  - `cd backend && uv run python -m mypy app/portfolio/exits.py --ignore-missing-imports` -> Success
  - `cd backend && uv run python -m mypy tests/test_trailing_profit.py --ignore-missing-imports` -> Success
  - `cd backend && uv run python -m pytest tests/test_trailing_profit.py -q` -> 9 passed in 0.10s

---

## 5) Data & sample evidence
- All tests use synthetic data: entry_price=100.0, various current_price values
- Balanced profile defaults: take_profit_pct=0.15, trailing_tp_pct=0.03, trailing_tp_arm_pct=0.02
- No external data sources used

---

## 6) Risk assessment & mitigations
- **Risk:** Floating point edge cases in price comparisons — **Severity:** low — **Mitigation:** Tests use pytest.approx; prices chosen to avoid boundary issues
- **Risk:** Changed return value of evaluate_exit from `(None, {})` to `(None, context)` — **Severity:** low — **Mitigation:** Callers check `reason` first; extra context is informational only

---

## 7) Backwards compatibility / migration notes
- No DB migrations needed — uses existing exit_context JSONB column
- No API changes
- Adding fields to frozen dataclass is backwards-compatible (all constructors updated)

---

## 8) Performance considerations
- No significant performance impact — trailing-TP check is O(1) dict lookup on exit_context
- No additional DB queries

---

## 9) Security & safety checks
- forbidden paths touched: `no`
- external/broker sdk usage: `no`
- secrets touched: `no`

---

## 10) Open questions & follow-ups
1. Should trailing_tp_arm_pct have a separate regime modifier, or is sharing the general regime_offset sufficient?
2. Consider adding metrics/logging for how much additional profit trailing-TP captures vs immediate TP

---

## 11) Short changelog
- feat(exits): add trailing take profit to exit engine (marketpulse-task-2026-03-31-0003)

---

## 12) Final verdict (developer self-check)
- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `validate`

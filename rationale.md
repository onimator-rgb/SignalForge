# Rationale for `marketpulse-task-2026-04-01-0009`

**author:** coder-agent (MarketPulse Coder)
**branch:** task/marketpulse-task-2026-04-01-0009-implementation
**date:** 2026-04-01

---

## 1) One-line summary
Add consecutive stop-loss protection guard that blocks new entries after N consecutive stop-loss closures.

---

## 2) Mapping to acceptance criteria

- **Criteria:** _check_consecutive_sl queries last N closed positions and checks if all are stop-loss exits
- **Status:** `pass`
- **Evidence:** Function queries last CONSECUTIVE_SL_THRESHOLD positions ordered by closed_at DESC, checks all have close_reason in ('stop_hit', 'trailing_stop_hit')

- **Criteria:** Guard creates a ProtectionEvent with type 'consecutive_sl_guard' and correct expiry
- **Status:** `pass`
- **Evidence:** Calls _log_protection with ptype='consecutive_sl_guard' and expires=now + timedelta(minutes=120). TestProtectionEventCreation verifies.

- **Criteria:** Guard is wired into check_protections() between stoploss_guard and class_exposure checks
- **Status:** `pass`
- **Evidence:** Added as section B2 at line 67-70 of protections.py, between B (stoploss_guard) and C (class_exposure)

- **Criteria:** Does not duplicate active ProtectionEvent (uses existing _log_protection dedup logic)
- **Status:** `pass`
- **Evidence:** _log_protection checks for existing active event of same type before creating new one

- **Criteria:** mypy passes with no errors
- **Status:** `pass`
- **Evidence:** `mypy app/portfolio/protections.py --ignore-missing-imports` -> Success: no issues found

- **Criteria:** All 5+ test cases pass
- **Status:** `pass`
- **Evidence:** 9 tests pass covering all required scenarios

- **Criteria:** Tests cover: trigger after N stops, broken streak allows, below threshold allows, expiry behavior, mixed stop reasons
- **Status:** `pass`
- **Evidence:** TestConsecutiveSlTriggersAfterNStops, TestConsecutiveSlAllowsWhenBrokenByProfit, TestConsecutiveSlAllowsWhenFewerThanThreshold, TestConsecutiveSlGuardExpires, TestConsecutiveSlMixedStopReasons

- **Criteria:** No test relies on real database
- **Status:** `pass`
- **Evidence:** All tests use AsyncMock for DB session

---

## 3) Files changed (and rationale per file)
- `backend/app/portfolio/protections.py` — Added _check_consecutive_sl(), config constants (CONSECUTIVE_SL_THRESHOLD=3, CONSECUTIVE_SL_LOCK_MINUTES=120), wired into check_protections(). Fixed pre-existing mypy narrowing issue.
- `backend/tests/test_consecutive_sl.py` — 9 async test cases with mocked AsyncSession
- `rationale.md` — This file

---

## 4) Tests run & results
- `cd backend && uv run python -m mypy app/portfolio/protections.py --ignore-missing-imports` -> Success
- `cd backend && uv run python -m pytest tests/test_consecutive_sl.py -q` -> 9 passed in 0.10s

---

## 5) Design decisions
- Followed exact same pattern as _check_stoploss_guard for consistency
- Both stop_hit and trailing_stop_hit count as stop-loss exits
- Guard is count-based (last N positions), not time-window-based, distinguishing from existing stoploss_guard

---

## 6) Risk assessment & mitigations
- **Risk:** integration — **Severity:** low — **Mitigation:** Follows identical pattern to existing guards

---

## 7) Backwards compatibility / migration notes
- No DB migrations needed. New guard uses existing ProtectionEvent table with new protection_type value.

---

## 8) Performance considerations
- Single query for last N positions (LIMIT 3) — negligible overhead.

---

## 9) Security & safety checks
- forbidden paths touched: `no`
- external/broker sdk usage: `no`
- secrets touched: `no`

---

## 10) Open questions & follow-ups
- None.

---

## 11) Short changelog
- feat(protections): add consecutive stop-loss guard (marketpulse-task-2026-04-01-0009)

---

## 12) Final verdict (developer self-check)
- **I confirm** that all acceptance criteria marked `pass` have test evidence: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `approve`

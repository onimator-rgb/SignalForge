# Rationale for `marketpulse-task-2026-04-01-0009`

**author:** coder-agent (MarketPulse Coder)
**branch:** task/marketpulse-task-2026-04-01-0009-implementation
**date:** 2026-04-01

---

## 1) One-line summary
Added consecutive stop-loss protection guard that blocks new entries when the last N closed positions were all stop-loss exits.

---

## 2) Mapping to acceptance criteria

- **Criteria:** _check_consecutive_sl queries last N closed positions and checks if all are stop-loss exits
- **Status:** `pass`
- **Evidence:** Function queries PortfolioPosition with status=closed, ordered by closed_at DESC, limit=CONSECUTIVE_SL_THRESHOLD, checks all close_reasons against {'stop_hit', 'trailing_stop_hit'}

- **Criteria:** Guard creates a ProtectionEvent with type 'consecutive_sl_guard' and correct expiry
- **Status:** `pass`
- **Evidence:** Calls _log_protection with ptype='consecutive_sl_guard', expires=now + timedelta(minutes=120). TestProtectionEventCreation verifies this.

- **Criteria:** Guard is wired into check_protections() between stoploss_guard and class_exposure checks
- **Status:** `pass`
- **Evidence:** Section B2 in check_protections(), lines 67-70

- **Criteria:** Does not duplicate active ProtectionEvent (uses existing _log_protection dedup logic)
- **Status:** `pass`
- **Evidence:** _log_protection checks for existing active event of same type before creating new one

- **Criteria:** mypy passes with no errors
- **Status:** `pass`
- **Evidence:** `mypy app/portfolio/protections.py --ignore-missing-imports` → Success: no issues found

- **Criteria:** All 5+ test cases pass
- **Status:** `pass`
- **Evidence:** 9 tests passed covering all scenarios

- **Criteria:** Tests cover: trigger after N stops, broken streak allows, below threshold allows, expiry behavior, mixed stop reasons
- **Status:** `pass`
- **Evidence:** TestConsecutiveSlTriggersAfterNStops, TestConsecutiveSlAllowsWhenBrokenByProfit, TestConsecutiveSlAllowsWhenFewerThanThreshold, TestConsecutiveSlGuardExpires, TestConsecutiveSlMixedStopReasons

- **Criteria:** No test relies on real database
- **Status:** `pass`
- **Evidence:** All tests use AsyncMock for db session

---

## 3) Files changed (and rationale per file)
- `backend/app/portfolio/protections.py` — added _check_consecutive_sl() guard function, config constants, wired into check_protections()
- `backend/tests/test_consecutive_sl.py` — 9 test cases covering all acceptance criteria scenarios
- `rationale.md` — this file

---

## 4) Tests run & results
- `cd backend && uv run python -m pytest tests/test_consecutive_sl.py -q` → 9 passed
- `cd backend && uv run python -m mypy app/portfolio/protections.py --ignore-missing-imports` → Success

---

## 5) Data & sample evidence
- All tests use synthetic mock data (AsyncMock side_effect lists)

---

## 6) Risk assessment & mitigations
- **Risk:** Integration with existing guards — **Severity:** low — **Mitigation:** follows exact same pattern as _check_stoploss_guard

---

## 7) Backwards compatibility / migration notes
- No database migrations needed (uses existing ProtectionEvent table with new protection_type value)
- No breaking changes to existing guards

---

## 8) Performance considerations
- Single query for last N closed positions (LIMIT 3) — negligible overhead

---

## 9) Security & safety checks
- forbidden paths touched: `no`
- external/broker sdk usage: `no`
- secrets touched: `no`
- API key logged: `no`

---

## 10) Open questions & follow-ups
- None

---

## 11) Short changelog
- feat(marketpulse-task-2026-04-01-0009): add consecutive stop-loss protection guard

---

## 12) Final verdict (developer self-check)
- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `approve`

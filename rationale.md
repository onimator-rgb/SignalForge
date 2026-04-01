# Rationale for `marketpulse-task-2026-04-01-0007`

**author:** coder-agent (MarketPulse Coder)
**branch:** task/marketpulse-task-2026-04-01-0007-implementation
**date:** 2026-04-01

---

## 1) One-line summary
Replace flat 24h asset cooldown with variable cooldown: 48h after a loss, 12h after a profit.

---

## 2) Mapping to acceptance criteria

- **Criteria:** _check_asset_cooldown queries the most recent closed position for the asset and reads its realized_pnl_usd
- **Status:** `pass`
- **Evidence:** Query uses `order_by(closed_at.desc()).limit(1)` and reads `realized_pnl_usd`

- **Criteria:** After a losing close (realized_pnl_usd < 0), re-entry is blocked for 48 hours
- **Status:** `pass`
- **Evidence:** test_loss_blocks_within_48h passes

- **Criteria:** After a profitable close (realized_pnl_usd >= 0), re-entry is blocked for 12 hours
- **Status:** `pass`
- **Evidence:** test_profit_blocks_within_12h passes

- **Criteria:** If no prior closed position exists for the asset, entry is allowed
- **Status:** `pass`
- **Evidence:** test_no_prior_closes_allows_entry passes

- **Criteria:** ProtectionEvent is logged with correct expires_at reflecting the variable cooldown
- **Status:** `pass`
- **Evidence:** test_protection_event_logged_with_correct_expiry passes

- **Criteria:** All tests pass and mypy reports no errors
- **Status:** `pass`
- **Evidence:** 7 passed, mypy Success: no issues found in 1 source file

---

## 3) Files changed (and rationale per file)
- `backend/app/portfolio/protections.py` — variable cooldown logic, new constants, 3-tuple return
- `backend/tests/test_buy_cooldown.py` — 7 unit tests covering all criteria + edge cases
- `rationale.md` — this file

---

## 4) Tests run & results
- `cd backend && uv run python -m pytest tests/test_buy_cooldown.py -q` → 7 passed
- `cd backend && uv run python -m mypy app/portfolio/protections.py --ignore-missing-imports` → Success

---

## 5) Design decisions
- 3-tuple return `(blocked, reason, cooldown_hours)` — minimal change, only one caller
- Zero PnL treated as non-loss (shorter 12h cooldown)
- Kept legacy `ASSET_COOLDOWN_HOURS` constant for backward compatibility

---

## 6) Risk assessment & mitigations
- **Risk:** 2-tuple → 3-tuple return signature — **Severity:** low — **Mitigation:** only one caller, updated together

---

## 7) Backwards compatibility / migration notes
- No DB migration needed. `ASSET_COOLDOWN_HOURS` kept but unused.

---

## 8) Performance considerations
- Changed from `count()` to `limit(1)` fetch — equivalent or better performance.

---

## 9) Security & safety checks
- forbidden paths touched: `no`
- external/broker sdk usage: `no`
- secrets touched: `no`

---

## 10) Open questions & follow-ups
None.

---

## 11) Short changelog
- feat(marketpulse-task-2026-04-01-0007): loss-aware variable buy cooldown

---

## 12) Final verdict (developer self-check)
- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `approve`

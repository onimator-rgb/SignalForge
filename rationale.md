# Rationale for `marketpulse-task-2026-04-01-0007`

**author:** coder-worker (MarketPulse Coder)
**branch:** task/marketpulse-task-2026-04-01-0007-implementation
**date:** 2026-04-01

---

## 1) One-line summary
Add Trailing Buy entry mechanism that trails price downward after buy signals and executes on bounce, reducing average entry cost.

---

## 2) Mapping to acceptance criteria

- **Criteria:** TrailingBuyState or equivalent dict-based state with all required fields
- **Status:** `pass`
- **Evidence:** `TrailingBuyState` dataclass + `start_trailing` returns dict with signal_price, lowest_price, bounce_pct, started_at, expires_at, status

- **Criteria:** start_trailing returns context_data dict with lowest_price=signal_price, correct expiry
- **Status:** `pass`
- **Evidence:** test_returns_valid_context asserts lowest_price == signal_price, expires_at == started_at + max_hours

- **Criteria:** update_trailing correctly detects bounce: buy triggered when price >= lowest * (1 + bounce_pct)
- **Status:** `pass`
- **Evidence:** test_triggers_buy_on_bounce: price drops to 90, bounces to 92 > 90*1.02=91.8, action='buy'

- **Criteria:** update_trailing correctly detects expiry when now >= expires_at
- **Status:** `pass`
- **Evidence:** test_expires_after_max_hours: time jumps 13h past 12h window, action='expired'

- **Criteria:** update_trailing tracks new lows: lowest_price decreases when price drops
- **Status:** `pass`
- **Evidence:** test_tracks_lower_price: price 95 < 100, lowest_price updated to 95

- **Criteria:** All 3 strategy profiles have trailing_buy_bounce_pct and trailing_buy_max_hours
- **Status:** `pass`
- **Evidence:** test_profile_has_trailing_buy_fields parametrized across all 3 profiles

- **Criteria:** All tests pass, mypy clean
- **Status:** `pass`
- **Evidence:** 14 passed, mypy: 0 errors in trailing_buy.py, profiles.py, service.py

- **Criteria:** New candidate_buy signals create EntryDecision with stage='trailing_buy' instead of immediate buy
- **Status:** `pass`
- **Evidence:** Phase 1b in _check_entries creates EntryDecision(stage='trailing_buy', status='pending')

- **Criteria:** Pending trailing buys are checked each cycle and updated with current price
- **Status:** `pass`
- **Evidence:** Phase 0 in _check_entries queries pending trail EntryDecisions and calls update_trailing

- **Criteria:** Buy executes when price bounces above trailing low by bounce_pct
- **Status:** `pass`
- **Evidence:** Phase 0 sets status='allowed', adds to ready_to_buy; Phase 2 opens position

- **Criteria:** Trailing buy expires gracefully after max_hours with proper EntryDecision update
- **Status:** `pass`
- **Evidence:** Phase 0 sets status='blocked', reason_codes=['trail_expired']

- **Criteria:** Assets with existing pending trails are not duplicated
- **Status:** `pass`
- **Evidence:** pending_trail_asset_ids set checked before creating new trails in Phase 1

---

## 3) Files changed (and rationale per file)
- `backend/app/strategy/profiles.py` — Added trailing_buy_bounce_pct and trailing_buy_max_hours to StrategyProfile dataclass and all 3 profile instances
- `backend/app/portfolio/trailing_buy.py` — New pure-function module: TrailingBuyState, start_trailing, update_trailing
- `backend/app/portfolio/service.py` — Integrated trailing buy into _check_entries with Phase 0 (process pending), Phase 1b (create new trails), Phase 2 (execute triggered buys)
- `backend/tests/test_trailing_buy.py` — 14 tests covering pure functions, profile params, and integration scenarios

---

## 4) Tests run & results
- `cd backend && uv run python -m pytest tests/test_trailing_buy.py -q` — 14 passed
- `cd backend && uv run python -m mypy app/portfolio/trailing_buy.py --ignore-missing-imports` — Success
- `cd backend && uv run python -m mypy app/strategy/profiles.py --ignore-missing-imports` — Success
- `cd backend && uv run python -m mypy app/portfolio/service.py --ignore-missing-imports` — 0 errors in service.py (pre-existing errors in other files only)

---

## 5) Data & sample evidence
- All tests use synthetic data with fixed timestamps and prices. No real market data.

---

## 6) Risk assessment & mitigations
- **Risk:** Modifying _check_entries is complex — **Severity:** medium — **Mitigation:** Preserved existing ranking/confirmation flow, added new phases around it, no changes to exit logic
- **Risk:** JSONB context_data shape — **Severity:** low — **Mitigation:** Pure functions validate and produce consistent dict structure

---

## 7) Backwards compatibility / migration notes
- No schema changes. Uses existing JSONB context_data column on EntryDecision.
- New trailing buy entries have stage='trailing_buy' which doesn't conflict with existing stages.

---

## 8) Performance considerations
- One additional DB query per cycle to load pending trailing buys. Negligible impact.

---

## 9) Security & safety checks
- forbidden paths touched: `no`
- external/broker sdk usage: `no`
- secrets touched: `no`
- API key logged: `no`

---

## 10) Open questions & follow-ups
1. Should ranking allocation_multiplier be applied to trailing buy position sizing?
2. Consider adaptive bounce thresholds based on asset volatility.
3. Backtest trailing buy fill rates vs immediate buy performance.

---

## 11) Short changelog
- feat(marketpulse-task-2026-04-01-0007): Add trailing buy entry mechanism

---

## 12) Final verdict (developer self-check)
- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `validate`

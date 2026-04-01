# Rationale for `marketpulse-task-2026-04-01-0029`

**author:** coder-agent
**branch:** task/marketpulse-task-2026-04-01-0029-implementation
**date:** 2026-04-01

---

## 1) One-line summary
Add a daily drawdown circuit breaker that halts all new position entries when portfolio equity drops more than 5% from the UTC day-open value.

---

## 2) Mapping to acceptance criteria

- **Criteria:** DAILY_DRAWDOWN_LIMIT_PCT = 5.0 is importable from rules.py
- **Status:** `pass`
- **Evidence:** `uv run python -c "from app.portfolio.rules import DAILY_DRAWDOWN_LIMIT_PCT; print(DAILY_DRAWDOWN_LIMIT_PCT)"` outputs `5.0`

- **Criteria:** _daily_drawdown_guard function exists and is async
- **Status:** `pass`
- **Evidence:** `async def _daily_drawdown_guard(db, portfolio_id, now)` at protections.py

- **Criteria:** check_protections calls _daily_drawdown_guard
- **Status:** `pass`
- **Evidence:** Guard F added in check_protections between entry_frequency_cap and risk-off checks

- **Criteria:** Uses ProtectionEvent model for both snapshot and block events
- **Status:** `pass`
- **Evidence:** Creates `daily_equity_snapshot` (status=expired) and `daily_drawdown` (status=active) ProtectionEvents

- **Criteria:** Expires at end of UTC day
- **Status:** `pass`
- **Evidence:** `expires_at=day_start + timedelta(days=1)` for both snapshot and block events

- **Criteria:** No DB migration required
- **Status:** `pass`
- **Evidence:** Uses existing ProtectionEvent table with JSONB context_data

- **Criteria:** All 6 tests pass
- **Status:** `pass`
- **Evidence:** `pytest tests/test_daily_drawdown.py -q` — 6 passed

- **Criteria:** Tests cover: below/above/exact threshold, snapshot creation, snapshot reuse, already-blocked early return
- **Status:** `pass`
- **Evidence:** Six test classes covering all scenarios

- **Criteria:** No database required — all DB calls mocked
- **Status:** `pass`
- **Evidence:** All tests use AsyncMock/MagicMock for session

- **Criteria:** mypy passes with no errors
- **Status:** `pass`
- **Evidence:** `mypy app/portfolio/protections.py --ignore-missing-imports` and `mypy tests/test_daily_drawdown.py --ignore-missing-imports` — both Success

---

## 3) Files changed (and rationale per file)

- `backend/app/portfolio/rules.py` — Added DAILY_DRAWDOWN_LIMIT_PCT = 5.0 constant (+1 LOC)
- `backend/app/portfolio/protections.py` — Added _daily_drawdown_guard async function and integrated into check_protections (+~70 LOC)
- `backend/tests/test_daily_drawdown.py` — 6 comprehensive unit tests with full async DB mocking (+~190 LOC)

---

## 4) Tests run & results

- **Commands run:**
  - `uv run python -c "from app.portfolio.rules import DAILY_DRAWDOWN_LIMIT_PCT; print(DAILY_DRAWDOWN_LIMIT_PCT)"` — output: 5.0
  - `uv run python -m mypy app/portfolio/protections.py --ignore-missing-imports` — Success
  - `uv run python -m pytest tests/test_daily_drawdown.py -q` — 6 passed
  - `uv run python -m mypy tests/test_daily_drawdown.py --ignore-missing-imports` — Success
- **Results summary:** All checks pass, no warnings

---

## 5) Data & sample evidence

- Synthetic test data: day_open_equity=1000, tested at 4% (960, allowed), 5% (950, blocked), 6% (940, blocked)
- No external data or fixtures required

---

## 6) Risk assessment & mitigations

- **Risk:** check_protections now computes current_equity with 2 extra DB queries — **Severity:** low — **Mitigation:** Queries are simple (single row + aggregate), and protections are checked infrequently (only on new entry candidates)
- **Risk:** Race condition on snapshot creation — **Severity:** low — **Mitigation:** Uses db.flush() within the existing transaction; duplicate snapshots are benign (first-found is used)

---

## 7) Backwards compatibility / migration notes

- API changes: None — existing `/portfolio/protections` endpoint will automatically surface daily_drawdown events
- DB migrations: None — uses existing ProtectionEvent table with JSONB context_data

---

## 8) Performance considerations

- Two additional SELECT queries per check_protections call (Portfolio cash + position sum)
- Negligible impact — these are indexed primary key and simple aggregate queries

---

## 9) Security & safety checks

- forbidden paths touched: `no`
- external/broker sdk usage: `no`
- secrets touched: `no`

---

## 10) Open questions & follow-ups

1. Should DAILY_DRAWDOWN_LIMIT_PCT be configurable per portfolio (stored in DB) rather than a global constant?
2. Should there be an admin endpoint to manually reset the daily drawdown block?

---

## 11) Short changelog

- `pending` — feat(protections): add daily drawdown circuit breaker [marketpulse-task-2026-04-01-0029]

---

## 12) Final verdict (developer self-check)

- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `validate`

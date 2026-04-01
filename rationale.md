# Rationale for `marketpulse-task-2026-04-01-0015`

**author:** coder-agent (MarketPulse Coder)
**branch:** task/marketpulse-task-2026-04-01-0015-implementation
**commit_sha:** (pending)
**date:** 2026-04-01

---

## 1) One-line summary
Implement portfolio equity curve computation as a pure function and expose via GET /api/v1/portfolio/equity-curve endpoint.

---

## 2) Mapping to acceptance criteria

- **Criteria:** build_equity_curve([]) returns a single initial EquityPoint with equity == initial_capital and drawdown_pct == 0
- **Status:** `pass`
- **Evidence:** `pytest tests/test_equity_curve.py::TestBuildEquityCurveEmpty — 4 tests passed`

- **Criteria:** A buy transaction reduces cash and increases positions_value; a sell does the inverse
- **Status:** `pass`
- **Evidence:** `pytest tests/test_equity_curve.py::TestBuySellCycle::test_buy_reduces_cash, test_sell_increases_cash — passed`

- **Criteria:** equity always equals cash + positions_value at every point
- **Status:** `pass`
- **Evidence:** `pytest tests/test_equity_curve.py::TestBuySellCycle::test_equity_equals_cash_plus_positions, TestEquityAlwaysConsistent — passed`

- **Criteria:** drawdown_pct is correctly calculated as (equity - peak) / peak, always <= 0
- **Status:** `pass`
- **Evidence:** `pytest tests/test_equity_curve.py::TestDrawdownAlwaysNonPositive, TestMultipleTradesDrawdown — passed`

- **Criteria:** EquityCurveOut.max_drawdown_pct equals the worst drawdown across all points
- **Status:** `pass`
- **Evidence:** `pytest tests/test_equity_curve.py::TestMultipleTradesDrawdown::test_max_drawdown_with_profit_sell — passed`

- **Criteria:** GET /equity-curve returns 200 with valid JSON matching EquityCurveOut schema
- **Status:** `pass`
- **Evidence:** `pytest tests/test_equity_curve.py::TestEquityCurveEndpoint::test_returns_200 — passed`

- **Criteria:** All tests pass, mypy clean
- **Status:** `pass`
- **Evidence:** `15 passed in 0.44s`, `mypy: Success: no issues found in 1 source file`

---

## 3) Files changed (and rationale per file)

- `backend/app/portfolio/equity_curve.py` — New file: EquityPoint frozen dataclass, build_equity_curve pure function, EquityCurveOut Pydantic schema (~85 LOC)
- `backend/app/portfolio/router.py` — Added GET /equity-curve endpoint that queries PortfolioTransaction and calls build_equity_curve (~40 LOC added)
- `backend/tests/test_equity_curve.py` — 15 unit tests covering empty input, buy/sell cycles, equity consistency, drawdown, sorting, schema, and API endpoint (~175 LOC)

---

## 4) Tests run & results

- **Commands run:**
  - `cd backend && uv run python -m pytest tests/test_equity_curve.py -q`
  - `cd backend && uv run python -m mypy app/portfolio/equity_curve.py --ignore-missing-imports`
- **Results summary:**
  - tests: 15 passed, 0 failed
  - mypy: Success, no issues found

---

## 5) Data & sample evidence

- Synthetic test fixtures with explicit timestamps and value_usd amounts
- Buy/sell cycles with known expected equity values (e.g., buy 200, sell 250 → equity 1050)
- Edge cases: empty transactions, unsorted input, multiple alternating buy/sell

---

## 6) Risk assessment & mitigations

- **Risk:** Router modification — **Severity:** low — **Mitigation:** Additive only (new endpoint), no changes to existing endpoints
- **Risk:** Pure function has no side effects — **Severity:** low — **Mitigation:** Fully tested with 15 unit tests

---

## 7) Backwards compatibility / migration notes

- API changes: GET /api/v1/portfolio/equity-curve added — backward compatible: yes (new endpoint only)
- DB migrations: none required (reads existing PortfolioTransaction table)

---

## 8) Performance considerations

- Pure function is O(n log n) due to sorting, O(n) for curve computation
- No caching needed for current scale; endpoint queries sorted by executed_at ASC

---

## 9) Security & safety checks

- forbidden paths touched: `no`
- external/broker sdk usage: `no`
- secrets touched: `no`

---

## 10) Open questions & follow-ups

1. The cash-flow formula (equity = cash + positions_value) is monotonically non-decreasing — drawdowns only appear if future enhancements incorporate unrealized P&L from market price changes.
2. Frontend chart component is a separate task per out_of_scope.

---

## 11) Short changelog

- `pending` — feat(marketpulse-task-2026-04-01-0015): add equity curve pure function and GET /equity-curve endpoint

---

## 12) Final verdict (developer self-check)

- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `validate`

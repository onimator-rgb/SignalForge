# Rationale for `marketpulse-task-2026-04-01-0005`

**author:** coder-agent (MarketPulse Coder)
**branch:** task/marketpulse-task-2026-04-01-0005-implementation
**date:** 2026-04-01

---

## 1) One-line summary
Enhance Sharpe ratio to use proper daily portfolio returns with sqrt(252) annualization and configurable risk-free rate.

---

## 2) Mapping to acceptance criteria

- **Criteria:** _compute_daily_returns groups positions by closed_at date and returns per-day summed returns
- **Status:** `pass`
- **Evidence:** test_daily_returns_grouping verifies 5 positions across 3 days produce correct sums

- **Criteria:** Sharpe uses sqrt(252) not sqrt(365)
- **Status:** `pass`
- **Evidence:** Formula updated, test_sharpe_known_values verifies exact value within 0.001

- **Criteria:** Sharpe subtracts daily risk_free_rate from mean daily return
- **Status:** `pass`
- **Evidence:** Formula: (mean_daily - rf/252) / std_daily * sqrt(252)

- **Criteria:** Sharpe requires >= 2 distinct trading days, returns None otherwise
- **Status:** `pass`
- **Evidence:** test_sharpe_single_day_returns_none confirms None for 1-day case

- **Criteria:** compute_risk_metrics accepts optional risk_free_rate parameter defaulting to 0.0
- **Status:** `pass`
- **Evidence:** Parameter added with default, existing callers unaffected

- **Criteria:** Existing Sortino, max_drawdown, profit_factor calculations remain unchanged
- **Status:** `pass`
- **Evidence:** All 15 existing tests in test_risk_metrics.py pass

- **Criteria:** Existing test_risk_metrics.py tests still pass
- **Status:** `pass`
- **Evidence:** 21 total tests pass (15 existing + 6 new)

- **Criteria:** test_sharpe_known_values verifies exact Sharpe value within 0.001 tolerance
- **Status:** `pass`
- **Evidence:** Manual calculation matches computed value

- **Criteria:** test_sharpe_with_risk_free_rate confirms rf > 0 lowers Sharpe
- **Status:** `pass`
- **Evidence:** rf=0.04 produces lower Sharpe than rf=0.0

- **Criteria:** Edge cases (single day, empty, None closed_at) all return Sharpe=None
- **Status:** `pass`
- **Evidence:** Three dedicated tests confirm None for each edge case

---

## 3) Files changed (and rationale per file)
- `backend/app/portfolio/risk_metrics.py` — added _compute_daily_returns helper, updated Sharpe formula to use daily returns with sqrt(252) and risk_free_rate
- `backend/tests/test_risk_metrics.py` — updated test_known_returns and test_zero_std_returns_none to use positions spanning multiple days
- `backend/tests/test_sharpe.py` — new comprehensive test file with 6 tests
- `rationale.md` — this file

---

## 4) Tests run & results
- `cd backend && uv run python -m pytest tests/test_sharpe.py -q` — 6 passed
- `cd backend && uv run python -m pytest tests/test_risk_metrics.py -q` — 15 passed
- `cd backend && uv run python -m mypy app/portfolio/risk_metrics.py --ignore-missing-imports` — Success

---

## 5) Data & sample evidence
- All test data is synthetic (SimpleNamespace mock positions)

---

## 6) Risk assessment & mitigations
- **Risk:** Changing Sharpe formula changes expected values in existing tests — **Severity:** medium — **Mitigation:** Updated test_known_returns to span multiple days and recalculated expected values

---

## 7) Backwards compatibility / migration notes
- risk_free_rate parameter defaults to 0.0, so existing callers need no changes
- Sortino ratio calculation unchanged (still uses per-trade returns)

---

## 8) Performance considerations
- O(n) grouping with defaultdict — negligible overhead for typical position counts

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
- feat(risk): daily-return Sharpe ratio with sqrt(252) and risk_free_rate

---

## 12) Final verdict (developer self-check)
- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `approve`

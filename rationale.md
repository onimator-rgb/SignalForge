# Rationale for `marketpulse-task-2026-04-01-0001`

**author:** coder-agent
**branch:** task/marketpulse-task-2026-04-01-0001-implementation
**commit_sha:** (pending)
**date:** 2026-04-01

---

## 1) One-line summary
Add avg_win_pct, avg_loss_pct, best_trade_pct, worst_trade_pct fields to risk metrics computation and schema.

---

## 2) Mapping to acceptance criteria

- **Criteria:** RiskMetricsResult dataclass has avg_win_pct, avg_loss_pct, best_trade_pct, worst_trade_pct fields
- **Status:** `pass`
- **Evidence:** `diff: backend/app/portfolio/risk_metrics.py` — 4 new fields added to dataclass

- **Criteria:** RiskMetricsOut schema has matching 4 new Optional[float] fields
- **Status:** `pass`
- **Evidence:** `diff: backend/app/portfolio/schemas.py` — 4 new fields added

- **Criteria:** All existing test_risk_metrics.py tests still pass without modification
- **Status:** `pass`
- **Evidence:** `pytest tests/test_risk_metrics.py -q` — 15 passed

- **Criteria:** mypy passes on both modified files
- **Status:** `pass`
- **Evidence:** `mypy app/portfolio/risk_metrics.py --ignore-missing-imports` — Success, `mypy app/portfolio/schemas.py --ignore-missing-imports` — Success

- **Criteria:** All new tests pass
- **Status:** `pass`
- **Evidence:** `pytest tests/test_profit_factor.py -q -v` — 13 passed

- **Criteria:** At least 12 test cases covering avg_win_pct, avg_loss_pct, best_trade_pct, worst_trade_pct
- **Status:** `pass`
- **Evidence:** 13 test cases in test_profit_factor.py

- **Criteria:** Edge cases covered: empty list, all wins, all losses, single trade, breakeven trade
- **Status:** `pass`
- **Evidence:** TestAvgWinLoss::test_empty_positions, test_avg_win_none_when_no_wins, test_avg_loss_none_when_no_losses, TestBestWorstTrade::test_single_position, test_all_negative, test_empty, TestProfitFactorExtended::test_breakeven_trade_excluded_from_avg

---

## 3) Files changed (and rationale per file)

- `backend/app/portfolio/risk_metrics.py` — Added 4 fields to RiskMetricsResult dataclass, computed avg_win_pct/avg_loss_pct/best_trade_pct/worst_trade_pct in compute_risk_metrics(), updated empty-positions early return. ~30 LOC added.
- `backend/app/portfolio/schemas.py` — Added 4 Optional[float] fields to RiskMetricsOut. ~4 LOC added.
- `backend/tests/test_profit_factor.py` — New test file with 13 test cases across 3 test classes. ~140 LOC.

---

## 4) Tests run & results

- **Commands run:**
  - `cd backend && uv run python -m pytest tests/test_profit_factor.py -q -v` — 13 passed
  - `cd backend && uv run python -m pytest tests/test_risk_metrics.py -q` — 15 passed
  - `cd backend && uv run python -m mypy app/portfolio/risk_metrics.py --ignore-missing-imports` — Success
  - `cd backend && uv run python -m mypy app/portfolio/schemas.py --ignore-missing-imports` — Success

---

## 5) Data & sample evidence

- Tests use synthetic SimpleNamespace objects with known pnl_pct/pnl_usd values
- Example: 3 wins [5.0, 10.0, 15.0] → avg_win_pct = 10.0
- Breakeven trade: pnl_usd=0.0 correctly excluded from win/loss averages

---

## 6) Risk assessment & mitigations

- **Risk:** Regression in existing metrics — **Severity:** low — **Mitigation:** Only added new fields; all 15 existing tests pass unchanged
- **Risk:** Breakeven trades miscounted — **Severity:** low — **Mitigation:** Dedicated test verifies pnl_usd=0 excluded from win/loss

---

## 7) Backwards compatibility / migration notes

- API: 4 new optional fields added to RiskMetricsOut — fully backward compatible (default None)
- DB migrations: none required (computed fields only)

---

## 8) Performance considerations

- Negligible: single additional pass over positions list for avg/best/worst computation
- No new DB queries or I/O

---

## 9) Security & safety checks

- forbidden paths touched: `no`
- external/broker sdk usage: `no`
- secrets touched: `no`

---

## 10) Open questions & follow-ups

1. Should the frontend display these new metrics in the risk dashboard?
2. Consider adding percentile-based metrics (e.g., 95th percentile loss) in a future task.

---

## 11) Short changelog

- (pending commit) — feat(risk-metrics): add avg_win_pct, avg_loss_pct, best/worst trade stats + tests

---

## 12) Final verdict (developer self-check)

- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `validate`

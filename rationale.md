# Rationale for `marketpulse-task-2026-04-01-0013`

**author:** coder-agent (MarketPulse Coder)
**branch:** task/marketpulse-task-2026-04-01-0013-implementation
**date:** 2026-04-01

---

## 1) One-line summary
Added Dollar Cost Averaging (DCA) engine that automatically buys more of a dropping position to reduce average entry cost, with all state stored in existing JSONB columns.

---

## 2) Mapping to acceptance criteria

- **Criteria:** get_dca_state returns default state when exit_context is None or has no DCA data
- **Status:** `pass`
- **Evidence:** test_default_when_exit_context_none, test_default_when_no_dca_key

- **Criteria:** should_dca returns True when price drops below threshold for current level
- **Status:** `pass`
- **Evidence:** test_first_level_triggers, test_second_level_triggers, test_third_level_triggers

- **Criteria:** should_dca returns False when max levels reached
- **Status:** `pass`
- **Evidence:** test_max_level_reached

- **Criteria:** calculate_dca_buy returns None when available cash is insufficient
- **Status:** `pass`
- **Evidence:** test_insufficient_cash

- **Criteria:** calculate_dca_buy uses level multiplier to scale position size
- **Status:** `pass`
- **Evidence:** test_level_multiplier_scaling

- **Criteria:** apply_dca_to_position correctly calculates weighted average entry price
- **Status:** `pass`
- **Evidence:** test_weighted_average_calculation, test_second_dca_buy_increments_level

- **Criteria:** evaluate_portfolio returns dca_count in summary dict
- **Status:** `pass`
- **Evidence:** Code inspection: return dict includes "dca_buys" key

- **Criteria:** _check_dca iterates open positions and triggers DCA when conditions met
- **Status:** `pass`
- **Evidence:** Code inspection: queries open positions, calls should_dca, executes buys

- **Criteria:** DCA buy creates a PortfolioTransaction with tx_type='dca_buy'
- **Status:** `pass`
- **Evidence:** Code inspection: PortfolioTransaction(tx_type="dca_buy") in _check_dca

- **Criteria:** Cash is deducted from portfolio after DCA buy
- **Status:** `pass`
- **Evidence:** Code: portfolio.current_cash -= dca_buy["buy_value"]

- **Criteria:** Slippage is applied to DCA buy price
- **Status:** `pass`
- **Evidence:** Code: adjusted_price = round(current_price * (1 + profile.slippage_buy_pct), 8)

- **Criteria:** Cash reserve (MIN_CASH_RESERVE_PCT) is respected
- **Status:** `pass`
- **Evidence:** Code: reserve = float(portfolio.initial_capital) * MIN_CASH_RESERVE_PCT

---

## 3) Files changed (and rationale per file)
- `backend/app/portfolio/dca.py` — New DCA engine with pure functions (get_dca_state, should_dca, calculate_dca_buy, apply_dca_to_position)
- `backend/app/portfolio/service.py` — Added _check_dca phase between exits and entries in evaluate_portfolio
- `backend/tests/test_dca.py` — 22 unit tests covering all DCA functions and edge cases
- `rationale.md` — This file

---

## 4) Tests run & results
- `cd backend && uv run python -c "from app.portfolio.dca import ..."` — passed (OK)
- `cd backend && uv run python -m mypy app/portfolio/dca.py --ignore-missing-imports` — passed (0 errors)
- `cd backend && uv run python -m pytest tests/test_dca.py -q` — passed (22 passed)

---

## 5) Data & sample evidence
- All tests use MagicMock positions with known numeric values
- Weighted average verified: (100*1 + 90*0.5) / 1.5 = 96.667

---

## 6) Risk assessment & mitigations
- **Risk:** Weighted average precision drift — **Severity:** medium — **Mitigation:** round to 8 decimal places matching model Numeric(24,8)
- **Risk:** Exit rule interaction after DCA — **Severity:** medium — **Mitigation:** stop_loss and take_profit recalculated from new weighted average

---

## 7) Backwards compatibility / migration notes
- No database migrations needed — DCA state stored in existing exit_context JSONB
- evaluate_portfolio return dict gains "dca_buys" key (additive, non-breaking)

---

## 8) Performance considerations
- One additional query per evaluate cycle (open positions, already cached in exit check)
- DCA check is O(n) over open positions (max 5)

---

## 9) Security & safety checks
- forbidden paths touched: `no`
- external/broker sdk usage: `no`
- secrets touched: `no`
- API key logged: `no`

---

## 10) Open questions & follow-ups
1. Consider adding DCA parameters (max_levels, drop_pct, multipliers) to StrategyProfile for per-profile customization
2. Frontend display of DCA state from exit_context

---

## 11) Short changelog
- feat(dca): add DCA evaluation engine with pure functions
- feat(portfolio): integrate DCA phase into evaluate_portfolio cycle
- test(dca): 22 unit tests for DCA logic

---

## 12) Final verdict (developer self-check)
- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `approve`

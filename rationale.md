# Rationale for `marketpulse-task-2026-04-02-0019`

**author:** coder-agent (MarketPulse Coder)
**branch:** task/marketpulse-task-2026-04-02-0019-implementation
**date:** 2026-04-02

---

## 1) One-line summary
Implement a pure-logic strategy advisor that analyzes backtest results and strategy rules to return prioritized, actionable improvement suggestions.

---

## 2) Mapping to acceptance criteria

- **Criteria:** suggest_improvements() accepts list[StrategyRule] and BacktestResult, returns list[str]
- **Status:** `pass`
- **Evidence:** Function signature matches spec; 16 tests confirm correct return type.

- **Criteria:** Returns actionable suggestions based on backtest metric thresholds (win_rate, drawdown, Sharpe, profit_factor)
- **Status:** `pass`
- **Evidence:** `test_low_win_rate`, `test_high_drawdown`, `test_low_sharpe`, `test_negative_profit_factor` all pass.

- **Criteria:** Analyzes rule structure (missing sell rules, all-same-action, empty rules)
- **Status:** `pass`
- **Evidence:** `test_no_rules_provided`, `test_all_buy_rules`, `test_all_sell_rules`, `test_no_sell_rules_triggers_suggestion` all pass.

- **Criteria:** Returns at most 5 suggestions, prioritized by severity
- **Status:** `pass`
- **Evidence:** `test_max_five_suggestions`, `test_drawdown_before_win_rate` pass.

- **Criteria:** All tests pass with pytest
- **Status:** `pass`
- **Evidence:** `pytest tests/test_strategy_advisor.py -q` — 16 passed in 0.08s

- **Criteria:** mypy passes with no errors
- **Status:** `pass`
- **Evidence:** `mypy app/ai_assistant/strategy_advisor.py --ignore-missing-imports` — Success: no issues found in 1 source file

---

## 3) Files changed (and rationale per file)

- `backend/app/ai_assistant/__init__.py` — Package init exporting StrategyRule and suggest_improvements (~3 LOC)
- `backend/app/ai_assistant/strategy_advisor.py` — Core logic: 10 heuristic rules, priority-sorted, capped at 5 suggestions (~120 LOC)
- `backend/tests/test_strategy_advisor.py` — 16 unit tests covering all heuristics, edge cases, cap, and priority ordering (~140 LOC)

---

## 4) Tests run & results

- **Commands run:**
  - `cd backend && uv run python -m pytest tests/test_strategy_advisor.py -q` — 16 passed in 0.08s
  - `cd backend && uv run python -m mypy app/ai_assistant/strategy_advisor.py --ignore-missing-imports` — Success: no issues

---

## 5) Data & sample evidence

All test data is synthetic (BacktestResult constructed via helper `_make_result()`). Threshold values match the task spec (win_rate < 0.4, drawdown < -0.15, Sharpe < 0.5, etc.).

---

## 6) Risk assessment & mitigations

- **Risk:** StrategyRule not defined elsewhere — **Severity:** low — **Mitigation:** Defined as a frozen dataclass within the module; can be moved to a shared models module in a future task.
- **Risk:** Integration with other modules — **Severity:** low — **Mitigation:** Only imports BacktestResult (frozen dataclass), no side effects.

---

## 7) Backwards compatibility / migration notes

No API changes, no DB migrations. New module only — fully additive.

---

## 8) Performance considerations

Pure synchronous function with O(n) rule scanning where n = number of rules. No performance concerns.

---

## 9) Security & safety checks

- forbidden paths touched: `no`
- external/broker sdk usage: `no`
- secrets touched: `no`

---

## 10) Open questions & follow-ups

1. Should StrategyRule be moved to a shared models module (e.g., `app.strategies.models`) when the strategies module is formalized?
2. Should the heuristic thresholds be configurable via settings rather than hardcoded constants?

---

## 11) Short changelog

- `feat(marketpulse-task-2026-04-02-0019): AI strategy advisor — suggest_improvements()` — 3 new files

---

## 12) Final verdict (developer self-check)

- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `validate`

# Rationale for `marketpulse-task-2026-04-01-0005`

**author:** coder-agent
**branch:** task/marketpulse-task-2026-04-01-0005-implementation
**commit_sha:** 40dc318aad32b26991ee5a951534ef9abfcfbd59
**date:** 2026-04-01

---

## 1) One-line summary
Pure-function backtest engine that simulates paper trades over a historical price series using StrategyProfile entry/exit rules.

---

## 2) Mapping to acceptance criteria

- **Criteria:** Trade dataclass is frozen with all specified fields
  **Status:** pass
  **Evidence:** `@dataclass(frozen=True) class Trade` with all 9 fields; `test_trade_is_frozen` confirms immutability.

- **Criteria:** simulate_trades returns empty list for empty/single price input
  **Status:** pass
  **Evidence:** `test_no_trades_on_empty_prices`, `test_no_trades_on_single_price` — both pass.

- **Criteria:** Stop loss triggers when price drops by stop_loss_pct from entry
  **Status:** pass
  **Evidence:** `test_stop_loss_triggered` — 10% drop exceeds balanced -8% SL → exit_reason='stop_loss'.

- **Criteria:** Take profit triggers when price rises by take_profit_pct from entry
  **Status:** pass
  **Evidence:** `test_take_profit_triggered` — 20% rise exceeds balanced 15% TP → exit_reason='take_profit'.

- **Criteria:** Max hold exit triggers after max_hold_hours bars
  **Status:** pass
  **Evidence:** `test_max_hold_exit` — flat prices for 80 bars, exit at bar 72 (max_hold_hours).

- **Criteria:** End of data closes any open position
  **Status:** pass
  **Evidence:** `test_end_of_data_closes_position` — 5-bar flat series → exit_reason='end_of_data'.

- **Criteria:** Slippage is applied to both entry and exit prices
  **Status:** pass
  **Evidence:** `test_slippage_applied` — entry_price ≈ 100*1.001, exit_price ≈ 120*0.999.

- **Criteria:** PnL and PnL% are calculated correctly including slippage
  **Status:** pass
  **Evidence:** `test_pnl_calculation` — exact match with manual calculation.

- **Criteria:** 1-bar cooldown between consecutive trades
  **Status:** pass
  **Evidence:** `test_cooldown_between_trades` — entry_index[1] - exit_index[0] == 2.

- **Criteria:** All tests pass, mypy clean
  **Status:** pass
  **Evidence:** `12 passed in 0.07s`, `mypy: Success: no issues found in 1 source file`.

---

## 3) Files changed (and rationale per file)

- `backend/app/backtest/__init__.py` — empty init to create the backtest package (+0 LOC)
- `backend/app/backtest/engine.py` — Trade dataclass + simulate_trades() pure function (+87 LOC)
- `backend/tests/test_backtest_engine.py` — 12 comprehensive tests (+119 LOC)

Total: ~206 LOC across 3 files (within limits).

---

## 4) Tests run & results

- **Commands run:**
  - `cd backend && uv run python -m pytest tests/test_backtest_engine.py -q`
  - `cd backend && uv run python -m mypy app/backtest/engine.py --ignore-missing-imports`
- **Results summary:**
  - tests: 12 passed, 0 failed (0.07s)
  - mypy: Success, no issues found

---

## 5) Data & sample evidence

All test data is synthetic — hand-crafted price lists:
- Stop loss: `[100.0, 90.0]` — 10% drop
- Take profit: `[100.0, 120.0]` — 20% rise
- Max hold: `[100.0] * 80` — flat for 80 bars
- Multiple trades: `[100.0, 120.0, 100.0, 100.0, 100.0]` — TP then end-of-data

---

## 6) Risk assessment & mitigations

- **Risk:** Integration with StrategyProfile — **Severity:** low — **Mitigation:** StrategyProfile is a stable frozen dataclass; only reads fields, no mutations.
- **Risk:** Float precision — **Severity:** low — **Mitigation:** pytest.approx used in all numeric assertions.

---

## 7) Backwards compatibility / migration notes

- No API changes, no DB changes. New module only — fully backward compatible.

---

## 8) Performance considerations

- Pure function, O(n) over price list. No concern for typical backtest sizes (<100k bars).

---

## 9) Security & safety checks

- forbidden paths touched: `no`
- external/broker sdk usage: `no`
- secrets touched: `no`

---

## 10) Open questions & follow-ups

1. Should the engine support short positions in the future?
2. Backtest metrics (Sharpe, max drawdown, etc.) are out of scope — separate task.

---

## 11) Short changelog

- `40dc318` — feat(backtest): add pure trade simulation engine — files: 3 — tests: 12 passed

---

## 12) Final verdict (developer self-check)

- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `validate`

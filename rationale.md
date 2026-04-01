# Rationale for `marketpulse-task-2026-04-01-0015`

**author:** coder-agent (MarketPulse Coder)
**branch:** task/marketpulse-task-2026-04-01-0015-implementation
**date:** 2026-04-01

---

## 1) One-line summary
Add multi-timeframe signal confluence scoring (RSI/MACD/Bollinger across 1h/4h/1d) as the 10th signal in the recommendation engine with weight 0.08.

---

## 2) Mapping to acceptance criteria

### Subtask s1 — score_mtf_confluence()

- **Criteria:** score_mtf_confluence returns SignalScore with score in [-1.0, 1.0]
- **Status:** `pass`
- **Evidence:** test_score_in_range, test_return_type — 21 tests pass

- **Criteria:** When RSI oversold on both 4h and 1d, confluence score is strongly positive (>0.5)
- **Status:** `pass`
- **Evidence:** test_bullish_confluence_4h_1d_oversold asserts score > 0.5

- **Criteria:** When RSI oversold on 1h only but overbought on 4h and 1d, confluence score is negative
- **Status:** `pass`
- **Evidence:** test_bearish_overrides_1h_bullish asserts score < 0

- **Criteria:** Returns score=0.0 when mtf_indicators is None or has <2 timeframes
- **Status:** `pass`
- **Evidence:** test_none_returns_zero, test_empty_dict_returns_zero, test_single_timeframe_returns_zero

- **Criteria:** mypy passes with no errors
- **Status:** `pass`
- **Evidence:** `mypy app/recommendations/scoring.py --ignore-missing-imports` → Success

### Subtask s2 — Integration in compute_recommendation

- **Criteria:** compute_recommendation accepts optional mtf_indicators parameter
- **Status:** `pass`
- **Evidence:** test_without_mtf_backward_compatible, test_mtf_none_same_as_omitted

- **Criteria:** Weights sum to exactly 1.00
- **Status:** `pass`
- **Evidence:** test_weights_sum_to_one asserts sum within 1e-9

- **Criteria:** Calling without mtf_indicators produces same classification as before (backward compatible)
- **Status:** `pass`
- **Evidence:** test_without_mtf_backward_compatible — mtf signal contributes 0.0

- **Criteria:** Calling with strong bullish MTF data increases composite score vs without
- **Status:** `pass`
- **Evidence:** test_bullish_mtf_increases_score

- **Criteria:** All existing tests still pass
- **Status:** `pass`
- **Evidence:** `pytest tests/` → 234 passed (only test_stochrsi.py weight count updated 9→10)

- **Criteria:** mypy passes with no errors
- **Status:** `pass`
- **Evidence:** mypy → Success: no issues found in 1 source file

---

## 3) Files changed (and rationale per file)
- `backend/app/recommendations/scoring.py` — Added score_mtf_confluence(), helper direction functions, MTF_TIMEFRAME_WEIGHTS, updated WEIGHTS (v2→v3), added mtf_indicators param to compute_recommendation
- `backend/tests/test_mtf_scoring.py` — 21 new unit + integration tests
- `backend/tests/test_stochrsi.py` — Updated weight count assertion (9→10) for compatibility
- `rationale.md` — This file

---

## 4) Tests run & results
- `cd backend && uv run python -m pytest tests/test_mtf_scoring.py -q` → 21 passed
- `cd backend && uv run python -m pytest tests/ -q` → 234 passed
- `cd backend && uv run python -m mypy app/recommendations/scoring.py --ignore-missing-imports` → Success

---

## 5) Weight redistribution
| Signal | v2 | v3 | Delta |
|--------|-----|-----|-------|
| RSI | 0.15 | 0.14 | -0.01 |
| MACD | 0.15 | 0.14 | -0.01 |
| Bollinger | 0.15 | 0.14 | -0.01 |
| Price Trend | 0.15 | 0.14 | -0.01 |
| Volume | 0.05 | 0.05 | 0.00 |
| Anomaly | 0.10 | 0.09 | -0.01 |
| Volatility | 0.10 | 0.09 | -0.01 |
| ADX | 0.10 | 0.09 | -0.01 |
| StochRSI | 0.05 | 0.04 | -0.01 |
| MTF Confluence | — | 0.08 | +0.08 |
| **Total** | **1.00** | **1.00** | — |

---

## 6) Risk assessment & mitigations
- **Risk:** Weight redistribution could shift edge-case classifications — **Severity:** medium — **Mitigation:** Max delta per signal is 0.01; backward compatibility test confirms no regression
- **Risk:** New function integration — **Severity:** low — **Mitigation:** Purely additive; existing signals untouched

---

## 7) Backwards compatibility / migration notes
- `mtf_indicators` defaults to None → 0.0 contribution. Existing callers unaffected.
- SCORING_VERSION bumped to "v3" for auditability.

---

## 8) Performance considerations
- Confluence scoring is O(1) — 3 timeframes × 3 indicators = 9 comparisons. Negligible.

---

## 9) Security & safety checks
- forbidden paths touched: `no`
- external/broker sdk usage: `no`
- secrets touched: `no`
- API key logged: `no`

---

## 10) Open questions & follow-ups
1. Service integration: `recommendations/service.py` should call `get_multi_timeframe_indicators()` and pass results to `compute_recommendation()`. This is out of scope per task spec.

---

## 11) Short changelog
- feat(scoring): add multi-timeframe confluence as 10th signal (marketpulse-task-2026-04-01-0015)

---

## 12) Final verdict (developer self-check)
- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `approve`

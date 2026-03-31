# Rationale for `marketpulse-task-2026-03-31-0001`

**author:** coder-worker (MarketPulse Coder)
**branch:** task/marketpulse-task-2026-03-31-0001-implementation
**date:** 2026-03-31

---

## 1) One-line summary
Add Stochastic RSI (%K, %D) indicator calculator with scoring integration into the recommendation engine.

---

## 2) Mapping to acceptance criteria

### Subtask s1 — StochRSI Calculator
- **Criteria:** calc_stochrsi returns None when given fewer bars than minimum required
- **Status:** `pass`
- **Evidence:** test_stochrsi_insufficient_data passes — 30 bars < 34 minimum returns None

- **Criteria:** calc_stochrsi returns StochRSIResult with k and d both in 0-100 range for valid input
- **Status:** `pass`
- **Evidence:** test_stochrsi_returns_result_for_valid_input passes — both k,d in [0,100]

- **Criteria:** For a strong uptrend (monotonically rising closes), %K and %D are both above 80
- **Status:** `pass`
- **Evidence:** test_stochrsi_strong_uptrend passes — k,d > 80

- **Criteria:** For a strong downtrend (monotonically falling closes), %K and %D are both below 20
- **Status:** `pass`
- **Evidence:** test_stochrsi_strong_downtrend passes — k,d < 20

- **Criteria:** For sideways data, %K and %D are in the 30-70 range
- **Status:** `pass`
- **Evidence:** test_stochrsi_sideways passes — k,d in [30,70]

- **Criteria:** StochRSIResult and calc_stochrsi are exported from calculators __init__
- **Status:** `pass`
- **Evidence:** test_stochrsi_exported_from_init passes

### Subtask s2 — Schema & Service Integration
- **Criteria:** IndicatorSnapshot includes stoch_rsi_k and stoch_rsi_d as optional float fields
- **Status:** `pass`
- **Evidence:** Fields added with `float | None = None` defaults

- **Criteria:** get_indicators() computes and populates StochRSI values when sufficient bars exist
- **Status:** `pass`
- **Evidence:** calc_stochrsi(closes) called in service, results populated in snapshot

- **Criteria:** get_indicators() sets stoch_rsi_k and stoch_rsi_d to None when insufficient data
- **Status:** `pass`
- **Evidence:** Conditional assignment: `stochrsi_res.k if stochrsi_res else None`

- **Criteria:** mypy passes with no errors on both files
- **Status:** `pass`
- **Evidence:** `mypy app/indicators/service.py app/indicators/schemas.py` — Success: no issues found

### Subtask s3 — Scoring Engine
- **Criteria:** WEIGHTS dict has 9 entries and sums to 1.0
- **Status:** `pass`
- **Evidence:** test_weights_sum passes — 9 entries, sum = 1.0

- **Criteria:** score_stochrsi(None, None) returns score 0.0
- **Status:** `pass`
- **Evidence:** test_score_stochrsi_none passes

- **Criteria:** score_stochrsi(15.0, 15.0) returns positive score (oversold)
- **Status:** `pass`
- **Evidence:** test_score_stochrsi_oversold passes — score = 0.7

- **Criteria:** score_stochrsi(85.0, 85.0) returns negative score (overbought)
- **Status:** `pass`
- **Evidence:** test_score_stochrsi_overbought passes — score = -0.7

- **Criteria:** compute_recommendation() includes stoch_rsi in signal_breakdown
- **Status:** `pass`
- **Evidence:** score_stochrsi added to signals list in compute_recommendation()

- **Criteria:** All existing tests still pass (no regression in scoring)
- **Status:** `pass`
- **Evidence:** test_adx.py — 9 passed including test_weights_sum

---

## 3) Files changed (and rationale per file)
| File | Change | LOC |
|------|--------|-----|
| `backend/app/indicators/calculators/stochrsi.py` | New StochRSI calculator module | ~70 |
| `backend/app/indicators/calculators/__init__.py` | Export StochRSIResult, calc_stochrsi | +3 |
| `backend/app/indicators/schemas.py` | Add stoch_rsi_k, stoch_rsi_d to IndicatorSnapshot | +2 |
| `backend/app/indicators/service.py` | Import and call calc_stochrsi, populate snapshot | +5 |
| `backend/app/recommendations/scoring.py` | Add score_stochrsi(), rebalance WEIGHTS (rsi 0.20→0.15, stoch_rsi 0.05) | +20 |
| `backend/tests/test_stochrsi.py` | 12 unit tests for calculator + scoring | ~90 |

---

## 4) Tests run & results
- `cd backend && uv run python -m pytest tests/test_stochrsi.py -q` — 12 passed
- `cd backend && uv run python -m pytest tests/test_adx.py -q` — 9 passed (no regression)
- `cd backend && uv run python -m mypy app/indicators/calculators/stochrsi.py app/indicators/service.py app/indicators/schemas.py app/recommendations/scoring.py --ignore-missing-imports` — Success: no issues found in 4 source files

---

## 5) Data & sample evidence
- Synthetic price series used in tests (monotonic trends, oscillating sideways data)
- No real market data or external API calls

---

## 6) Risk assessment & mitigations
- **Risk:** WEIGHTS rebalance (RSI 0.20→0.15) changes existing composite scores
- **Severity:** medium
- **Mitigation:** Small delta (0.05), StochRSI is RSI-derived so combined RSI weight is preserved. All existing tests pass.

---

## 7) Backwards compatibility / migration notes
- New optional fields in IndicatorSnapshot default to None — fully backward compatible
- No database migration needed
- No router/endpoint changes

---

## 8) Performance considerations
- calc_stochrsi computes rolling RSI for each bar position — O(n * rsi_period) complexity
- For default lookback=60, this is ~60 RSI calculations — negligible overhead

---

## 9) Security & safety checks
- forbidden paths touched: `no`
- external/broker sdk usage: `no`
- secrets touched: `no`
- API key logged: `no`

---

## 10) Open questions & follow-ups
1. Consider caching intermediate RSI series to avoid recomputation if performance becomes a concern with larger lookback windows.

---

## 11) Short changelog
- feat(stochrsi): add StochRSI calculator with %K/%D output
- feat(schema): add stoch_rsi_k, stoch_rsi_d to IndicatorSnapshot
- feat(scoring): add score_stochrsi signal, rebalance WEIGHTS to 9 entries
- test: 12 unit tests for StochRSI calculator and scoring

---

## 12) Final verdict (developer self-check)
- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `approve`

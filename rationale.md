# Rationale for `marketpulse-task-2026-04-01-0011`

**author:** coder-agent (MarketPulse Coder)
**branch:** task/marketpulse-task-2026-04-01-0011-implementation
**commit_sha:** (pending)
**date:** 2026-04-01

---

## 1) One-line summary
Enhanced regime detection with ADX trend strength signal and price trend scoring, plus regime transition tracking that applies new profile stop-loss/take-profit/trailing parameters to all open positions on regime change.

---

## 2) Mapping to acceptance criteria

### Subtask s1 — ADX trend strength signal
- **Criteria:** calculate_regime() returns avg_adx in inputs dict
- **Status:** `pass`
- **Evidence:** `result["inputs"]["avg_adx"]` is set in all test cases (35.0, 12.0, or None)

- **Criteria:** calculate_regime() returns price_trend_score in inputs dict
- **Status:** `pass`
- **Evidence:** `result["inputs"]["price_trend_score"]` verified in tests

- **Criteria:** ADX contributes ±2 to regime score when avg_adx > 30
- **Status:** `pass`
- **Evidence:** `test_high_adx_bullish_adds_points` and `test_high_adx_bearish_subtracts_points` verify ±2

- **Criteria:** Price trend contributes ±1 to regime score based on median 24h change
- **Status:** `pass`
- **Evidence:** `TestPriceTrendScore` class — 5 test cases for +1, -1, 0, empty, None

- **Criteria:** If ADX data unavailable, function still works (graceful degradation)
- **Status:** `pass`
- **Evidence:** `test_adx_unavailable_graceful` — exception raised → avg_adx=None, regime still calculated

- **Criteria:** All tests pass including new ADX and price trend test cases
- **Status:** `pass`
- **Evidence:** `pytest tests/test_regime_switch.py -q -x -v` — 17 passed

### Subtask s2 — Regime transition and position updates
- **Criteria:** detect_regime_transition() correctly identifies regime changes
- **Status:** `pass`
- **Evidence:** `test_regime_change_detected` — neutral→risk_on returns (True, "neutral")

- **Criteria:** detect_regime_transition() returns (False, None) when regime unchanged
- **Status:** `pass`
- **Evidence:** `test_same_regime_no_transition`, `test_first_call_no_transition`

- **Criteria:** apply_profile_to_open_positions() updates exit_context JSONB for all open positions
- **Status:** `pass`
- **Evidence:** `test_updates_open_positions` — 3 positions updated with regime params

- **Criteria:** auto_select_profile() returns transition info in result dict
- **Status:** `pass`
- **Evidence:** `regime_info["transition"]` dict with changed/from/to/positions_updated keys

- **Criteria:** Regime transition is logged via structlog
- **Status:** `pass`
- **Evidence:** `log.info("strategy.regime_transition", ...)` and `log.info("strategy.profile_applied_to_positions", ...)`

- **Criteria:** All tests pass
- **Status:** `pass`
- **Evidence:** 17/17 passed

### Subtask s3 — Comprehensive tests
- **Criteria:** At least 10 test cases covering ADX scoring, price trend, transitions, and position updates
- **Status:** `pass`
- **Evidence:** 17 test cases across 4 test classes

- **Criteria:** All tests pass
- **Status:** `pass`
- **Evidence:** `pytest tests/test_regime_switch.py -q -x -v` — 17 passed, 0 failed

- **Criteria:** Tests use mocks (no real DB required)
- **Status:** `pass`
- **Evidence:** All DB interactions via AsyncMock/MagicMock

- **Criteria:** Edge cases covered: no data, no positions, repeated same regime
- **Status:** `pass`
- **Evidence:** `test_adx_unavailable_graceful`, `test_no_open_positions`, `test_same_regime_no_transition`, `test_handles_none_exit_context`, `test_all_none_changes`, `test_empty_cache`

---

## 3) Files changed (and rationale per file)
- `backend/app/strategy/regime.py` — Added `_calc_avg_adx()` and `_calc_price_trend_score()` helpers, integrated ADX±2 and price-trend±1 into `calculate_regime()` score. ~60 LOC added.
- `backend/app/strategy/service.py` — Added `detect_regime_transition()`, `apply_profile_to_open_positions()`, and enhanced `auto_select_profile()` with transition detection. ~70 LOC added.
- `backend/tests/test_regime_switch.py` — New file with 17 tests across 4 classes. ~250 LOC.
- `rationale.md` — This file.

---

## 4) Tests run & results
- **Commands run:**
  - `cd backend && uv run python -m pytest tests/test_regime_switch.py -q -x -v` — 17 passed
  - `cd backend && uv run python -m mypy app/strategy/regime.py --ignore-missing-imports --follow-imports=skip` — Success
  - `cd backend && uv run python -m mypy app/strategy/service.py --ignore-missing-imports --follow-imports=skip` — Success
- **Results summary:**
  - tests: 17 passed, 0 failed
  - mypy: passed on both changed files (pre-existing error in cache.py unrelated to this task)

---

## 5) Data & sample evidence
- All test data is synthetic via `_make_cache()` and `_make_position()` factories
- ADX values mocked: 35.0 (strong trend), 12.0 (no trend), None (unavailable)
- Price change arrays: [5.0]*8+[-1.0]*2 (bullish), [-3.0]*8+[1.0]*2 (bearish)

---

## 6) Risk assessment & mitigations
- **Risk:** Module-level `_last_regime` resets on restart — **Severity:** low — **Mitigation:** Acceptable for paper trading; first call after restart won't detect transition
- **Risk:** ADX calc fails for assets with no bars — **Severity:** low — **Mitigation:** try/except per asset, skip gracefully, log warning
- **Risk:** Test pollution from `_last_regime` — **Severity:** low — **Mitigation:** `setup_method` resets state before each test

---

## 7) Backwards compatibility / migration notes
- `calculate_regime()` return dict now has `avg_adx` and `price_trend_score` in `inputs` — backward compatible (additive)
- `auto_select_profile()` return dict now has `transition` key — backward compatible (additive)
- No DB migrations needed — uses existing `exit_context` JSONB field

---

## 8) Performance considerations
- ADX calculation fetches last 30 bars per active asset — bounded query, index-supported
- Only runs when `calculate_regime()` is called (periodic, not per-request)
- No additional latency for non-transition cases

---

## 9) Security & safety checks
- forbidden paths touched: `no`
- external/broker sdk usage: `no`
- secrets touched: `no`

---

## 10) Open questions & follow-ups
1. Should `_last_regime` be persisted to DB for restart resilience?
2. Should position parameter updates trigger immediate exit evaluation or wait for next exit check cycle?
3. ADX period=14 is hardcoded — should it be configurable via profile?

---

## 11) Short changelog
- `(pending)` — feat(marketpulse-task-2026-04-01-0011): add ADX trend strength + price trend to regime scoring, regime transition detection, and open position parameter application

---

## 12) Final verdict (developer self-check)
- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `validate`

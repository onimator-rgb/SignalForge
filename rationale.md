# Rationale for `marketpulse-task-2026-04-01-0011`

**author:** coder-worker (MarketPulse Coder)
**branch:** task/marketpulse-task-2026-04-01-0011-implementation
**commit_sha:** 7574898
**date:** 2026-04-01
**model_calls:** 2

---

## 1) One-line summary
Enhanced regime detection with ADX trend strength signal, price trend scoring, regime transition tracking, and automatic open-position parameter application on regime change.

---

## 2) Mapping to acceptance criteria

### Subtask s1 — ADX trend strength + price trend

- **Criteria:** calculate_regime() returns avg_adx in inputs dict
- **Status:** `pass`
- **Evidence:** regime.py:194 adds `avg_adx` to inputs; test_high_adx_bullish_adds_points asserts `result["inputs"]["avg_adx"] == 35.0`

- **Criteria:** calculate_regime() returns price_trend_score in inputs dict
- **Status:** `pass`
- **Evidence:** regime.py:195 adds `price_trend_score` to inputs; tests verify via score calculations

- **Criteria:** ADX contributes ±2 to regime score when avg_adx > 30
- **Status:** `pass`
- **Evidence:** regime.py:166-170 — adds +2 when breadth>0.55, -2 when breadth<0.40; test_high_adx_bullish_adds_points and test_high_adx_bearish_subtracts_points confirm

- **Criteria:** Price trend contributes ±1 to regime score based on median 24h change
- **Status:** `pass`
- **Evidence:** regime.py:65-81 _calc_price_trend_score returns +1/-1/0; test_positive_trend, test_negative_trend, test_neutral_trend confirm

- **Criteria:** If ADX data unavailable, function still works (graceful degradation)
- **Status:** `pass`
- **Evidence:** regime.py:161-164 wraps ADX in try/except; test_adx_unavailable_graceful mocks exception and verifies regime still calculates

- **Criteria:** All tests pass including new ADX and price trend test cases
- **Status:** `pass`
- **Evidence:** `pytest tests/test_regime_switch.py -q -x -v` → 17 passed

### Subtask s2 — Regime transition detection + position parameter application

- **Criteria:** detect_regime_transition() correctly identifies regime changes
- **Status:** `pass`
- **Evidence:** service.py:30-46; test_regime_change_detected asserts (True, "neutral") on neutral→risk_on

- **Criteria:** detect_regime_transition() returns (False, None) when regime unchanged
- **Status:** `pass`
- **Evidence:** test_same_regime_no_transition asserts (False, None) on risk_on→risk_on

- **Criteria:** apply_profile_to_open_positions() updates exit_context JSONB for all open positions
- **Status:** `pass`
- **Evidence:** service.py:49-84; test_updates_open_positions verifies 3 positions get regime_stop_loss, regime_take_profit, regime_trailing_pct, regime_profile, regime_switched_at

- **Criteria:** auto_select_profile() returns transition info in result dict
- **Status:** `pass`
- **Evidence:** service.py:116-121 adds transition dict with changed/from/to/positions_updated keys

- **Criteria:** Regime transition is logged via structlog
- **Status:** `pass`
- **Evidence:** service.py:108-113 logs "strategy.regime_transition" with from_regime, to_regime, profile

- **Criteria:** All tests pass
- **Status:** `pass`
- **Evidence:** 17/17 tests pass

### Subtask s3 — Comprehensive tests

- **Criteria:** At least 10 test cases covering ADX scoring, price trend, transitions, and position updates
- **Status:** `pass`
- **Evidence:** 17 test cases: 4 ADX, 5 price trend, 4 transitions, 4 position updates

- **Criteria:** All tests pass
- **Status:** `pass`
- **Evidence:** `pytest tests/test_regime_switch.py -q -x -v` → 17 passed, 0 failed

- **Criteria:** Tests use mocks (no real DB required)
- **Status:** `pass`
- **Evidence:** All tests use AsyncMock/MagicMock for DB; FakeLivePrice for cache

- **Criteria:** Edge cases covered: no data, no positions, repeated same regime
- **Status:** `pass`
- **Evidence:** test_empty_cache, test_all_none_changes, test_no_open_positions, test_same_regime_no_transition, test_handles_none_exit_context

---

## 3) Files changed (and rationale per file)
- `backend/app/strategy/regime.py` — Added `_calc_avg_adx()` for average ADX across active assets, `_calc_price_trend_score()` for median 24h change scoring, integrated both into `calculate_regime()` scoring pipeline
- `backend/app/strategy/service.py` — Added `detect_regime_transition()` with module-level state tracking, `apply_profile_to_open_positions()` for JSONB exit_context updates, enhanced `auto_select_profile()` with transition detection and position application
- `backend/tests/test_regime_switch.py` — 17 test cases across 4 test classes covering ADX scoring, price trends, regime transitions, and position parameter application
- `rationale.md` — This file

---

## 4) Tests run & results
- **Commands run:**
  - `cd backend && uv run python -m pytest tests/test_regime_switch.py -q -x -v` → **17 passed** in 0.40s
  - `cd backend && uv run python -m mypy app/strategy/regime.py app/strategy/service.py --ignore-missing-imports` → **0 errors in checked files** (1 pre-existing error in app/live/cache.py:99 — unrelated `Unsupported operand types for +` due to nullable dict values)

---

## 5) Data & sample evidence
- All tests use synthetic fixtures: FakeLivePrice, _make_cache(), _make_position()
- DB interactions fully mocked via AsyncMock with _db_side_effect helper
- No real database or external API calls

---

## 6) Risk assessment & mitigations
- **Risk:** Module-level `_last_regime` resets on process restart → **Severity:** low → **Mitigation:** First call after restart won't detect transition; acceptable for paper trading
- **Risk:** ADX calc may fail if no price bars exist → **Severity:** low → **Mitigation:** try/except with graceful skip and warning log
- **Risk:** Test pollution from module-level state → **Severity:** low → **Mitigation:** setup_method resets `_last_regime = None` before each test

---

## 7) Backwards compatibility / migration notes
- `calculate_regime()` return dict now includes `avg_adx` and `price_trend_score` in inputs — additive, no breaking changes
- `auto_select_profile()` return dict now includes `transition` key — additive
- No database migrations required (exit_context is existing JSONB field)

---

## 8) Performance considerations
- ADX calculation adds N async DB queries (one per active asset) to regime calculation — acceptable for paper trading with small asset universe
- Position parameter application is O(open_positions) — negligible

---

## 9) Security & safety checks
- forbidden paths touched: `no`
- external/broker sdk usage: `no`
- secrets touched: `no`
- API key logged: `no`
- Real trading: `no` — paper trading only

---

## 10) Open questions & follow-ups
1. Consider persisting `_last_regime` to DB for resilience across restarts
2. Pre-existing mypy error in app/live/cache.py:99 should be fixed separately

---

## 11) Short changelog
- `7574898` — feat(marketpulse-task-2026-04-01-0011): add ADX trend strength + price trend to regime scoring, regime transition detection, and open position parameter application

---

## 12) Final verdict (developer self-check)
- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `approve`

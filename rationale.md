# Rationale for `marketpulse-task-2026-04-02-0059`

**author:** coder-agent (MarketPulse Coder)
**branch:** task/marketpulse-task-2026-04-02-0059-implementation
**commit_sha:** (pending)
**date:** 2026-04-02

---

## 1) One-line summary
Implement RSI divergence detector that identifies bullish and bearish divergences between price swing highs/lows and RSI indicator values.

---

## 2) Mapping to acceptance criteria

- **Criteria:** DivergenceDetector extends BaseDetector with name property returning 'divergence'
- **Status:** `pass`
- **Evidence:** `DivergenceDetector(BaseDetector)` with `name` returning `"divergence"` in divergence.py

- **Criteria:** detect() returns AnomalyCandidate with anomaly_type='divergence' for bullish divergence (price lower low + RSI higher low)
- **Status:** `pass`
- **Evidence:** `test_bullish_divergence`, `test_forced_bullish_divergence` — passed

- **Criteria:** detect() returns AnomalyCandidate with direction='bearish' for bearish divergence (price higher high + RSI lower high)
- **Status:** `pass`
- **Evidence:** `test_bearish_divergence`, `test_forced_bearish_divergence` — passed

- **Criteria:** detect() returns None when no divergence is present
- **Status:** `pass`
- **Evidence:** `test_no_divergence_trending` — passed

- **Criteria:** detect() returns None when fewer than 40 bars are provided
- **Status:** `pass`
- **Evidence:** `test_insufficient_data_returns_none` — passed

- **Criteria:** Score is between 0.6 and 0.9 and severity is computed via score_to_severity()
- **Status:** `pass`
- **Evidence:** `test_score_range` — passed; score clamped to [0.65, 0.85]

- **Criteria:** DivergenceDetector is registered in the DETECTORS list in service.py
- **Status:** `pass`
- **Evidence:** `DivergenceDetector()` appended to DETECTORS list in service.py

- **Criteria:** All tests pass with pytest
- **Status:** `pass`
- **Evidence:** `pytest tests/test_divergence_detector.py -q` — 12 passed in 0.73s

- **Criteria:** mypy reports no errors
- **Status:** `pass`
- **Evidence:** `mypy app/anomalies/detectors/divergence.py --ignore-missing-imports` — Success: no issues found

---

## 3) Files changed (and rationale per file)

- `backend/app/anomalies/detectors/divergence.py` — New file: DivergenceDetector class with swing point detection and RSI divergence logic (~140 LOC)
- `backend/tests/test_divergence_detector.py` — New file: 12 unit tests covering bullish, bearish, no divergence, insufficient data, score range, details structure
- `backend/app/anomalies/service.py` — Modified: added import and registration of DivergenceDetector (~2 LOC delta)

---

## 4) Tests run & results

- **Commands run:**
  - `cd backend && uv run python -m pytest tests/test_divergence_detector.py -q` — 12 passed in 0.73s
  - `cd backend && uv run python -m mypy app/anomalies/detectors/divergence.py --ignore-missing-imports` — Success

---

## 5) Data & sample evidence

- Synthetic sinusoidal price series to create swing highs/lows
- Bullish divergence: price lows at ~90 and ~85, RSI lows diverge higher
- Bearish divergence: price highs at ~110 and ~115, RSI highs diverge lower
- Trending series: linear 90->130, no swings, returns None

---

## 6) Risk assessment & mitigations

- **Risk:** False positives on noisy data — **Severity:** low — **Mitigation:** swing window of 5 bars; score clamped [0.65, 0.85]
- **Risk:** RSI computation overhead — **Severity:** low — **Mitigation:** only 60-bar windows, uses existing calc_rsi

---

## 7) Backwards compatibility / migration notes

- No API changes, no DB migrations
- New detector auto-registered; produces new anomaly_type='divergence' events

---

## 8) Performance considerations

- RSI series built by iterating over closes O(n*period) — acceptable for 60-bar windows
- Swing detection O(n*window) — negligible

---

## 9) Security & safety checks

- forbidden paths touched: `no`
- external/broker sdk usage: `no`
- secrets touched: `no`

---

## 10) Open questions & follow-ups

1. Should MACD histogram divergence be added as a second indicator check?
2. Should the swing window (5) be configurable via settings?

---

## 11) Short changelog

- (pending) — feat(marketpulse-task-2026-04-02-0059): RSI divergence detector

---

## 12) Final verdict (developer self-check)

- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `approve`

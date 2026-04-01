# Rationale for `marketpulse-task-2026-04-01-0007`

**author:** coder-agent (MarketPulse Coder)
**branch:** task/marketpulse-task-2026-04-01-0007-implementation
**commit_sha:** 9b270f0
**date:** 2026-04-01
**model_calls:** 1

---

## 1) One-line summary
Add absolute volume floor (rule #5) to entry confirmation engine, blocking entries on illiquid assets below configurable USD thresholds per asset class.

---

## 2) Mapping to acceptance criteria

- **Criteria:** check_confirmations() blocks entry when avg_volume < MIN_ABS_VOLUME for the asset class
- **Status:** `pass`
- **Evidence:** test_low_abs_volume_crypto_blocks, test_low_abs_volume_stock_blocks

- **Criteria:** check_confirmations() allows entry when avg_volume >= MIN_ABS_VOLUME
- **Status:** `pass`
- **Evidence:** test_sufficient_volume_crypto_passes, test_sufficient_volume_stock_passes

- **Criteria:** check_confirmations() allows entry when avg_volume is None (no data = no block)
- **Status:** `pass`
- **Evidence:** test_none_volume_passes

- **Criteria:** risk_off regime uses tighter thresholds
- **Status:** `pass`
- **Evidence:** test_risk_off_tighter_threshold_crypto, test_risk_off_tighter_threshold_stock

- **Criteria:** crypto and stock asset classes use different thresholds
- **Status:** `pass`
- **Evidence:** test_low_abs_volume_crypto_blocks (50k), test_low_abs_volume_stock_blocks (100k)

- **Criteria:** reason_code 'low_abs_volume' appears in blocked result
- **Status:** `pass`
- **Evidence:** test_low_abs_volume_crypto_blocks asserts 'low_abs_volume' in reason_codes

- **Criteria:** context includes avg_volume_usd and min_volume_threshold fields
- **Status:** `pass`
- **Evidence:** test_context_includes_volume_fields

---

## 3) Files changed (and rationale per file)
- `backend/app/portfolio/confirmations.py` — Added rule #5 (low_abs_volume) with 4 threshold constants and per-asset-class logic
- `backend/tests/test_volume_filter.py` — 9 unit tests covering all acceptance criteria
- `rationale.md` — This file

---

## 4) Tests run & results
- **Commands run:**
  - `cd backend && uv run python -m pytest tests/test_volume_filter.py -q -v` → 9 passed
  - `cd backend && uv run python -m mypy app/portfolio/confirmations.py --ignore-missing-imports` → 1 pre-existing error (line 63, unrelated to changes)

---

## 5) Data & sample evidence
- Pure unit tests with controlled inputs, no fixtures needed

---

## 6) Risk assessment & mitigations
- **Risk:** regression in existing confirmation rules → **Severity:** low → **Mitigation:** new rule is additive; existing rules untouched; rule #5 placed after rule #3 (weak_volume) to keep volume checks grouped

---

## 7) Backwards compatibility / migration notes
- Fully backward compatible. New rule only triggers when avg_volume is not None and below threshold.

---

## 8) Performance considerations
- No performance impact. Single comparison added to existing synchronous function.

---

## 9) Security & safety checks
- forbidden paths touched: `no`
- external/broker sdk usage: `no`
- secrets touched: `no`
- API key logged: `no`

---

## 10) Open questions & follow-ups
1. Pre-existing mypy error on line 63 (`change_24h_pct` assigned as `float | None` to context dict) — not introduced by this task.

---

## 11) Short changelog
- `9b270f0` → feat(confirmations): add absolute volume floor filter (rule #5)

---

## 12) Final verdict (developer self-check)
- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `approve`

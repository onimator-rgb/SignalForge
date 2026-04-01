# Rationale for `marketpulse-task-2026-04-01-0011`

**author:** coder-agent
**branch:** task/marketpulse-task-2026-04-01-0011-implementation
**date:** 2026-04-01

---

## 1) One-line summary
Add stateless FastAPI endpoints to list available bot presets and generate strategy rules from them.

---

## 2) Mapping to acceptance criteria

- **Criteria:** GET /api/v1/strategies/presets returns 200 with a JSON list of 3 preset descriptors (grid, dca, btd)
- **Status:** `pass`
- **Evidence:** `pytest tests/test_presets_api.py::test_list_presets_returns_200_with_three_presets — passed`

- **Criteria:** Each preset descriptor includes preset_type, display_name, description, and params array with name/type/description
- **Status:** `pass`
- **Evidence:** `pytest tests/test_presets_api.py::test_list_presets_contains_required_fields — passed`

- **Criteria:** POST /api/v1/strategies/from-preset with {preset_type: 'dca', params: {interval_hours: 4, amount_per_buy: 50, max_buys: 10}} returns 200 with generated rules
- **Status:** `pass`
- **Evidence:** `pytest tests/test_presets_api.py::test_generate_dca_rules — passed`

- **Criteria:** POST /api/v1/strategies/from-preset with unknown preset_type returns 422
- **Status:** `pass`
- **Evidence:** `pytest tests/test_presets_api.py::test_unknown_preset_type_returns_422 — passed`

- **Criteria:** POST /api/v1/strategies/from-preset with invalid params (e.g. negative values) returns 422 with descriptive error
- **Status:** `pass`
- **Evidence:** `pytest tests/test_presets_api.py::test_invalid_params_negative_amount_returns_422 — passed`

- **Criteria:** All tests pass, mypy clean
- **Status:** `pass`
- **Evidence:** `7 passed in 0.11s`, `mypy: Success: no issues found in 2 source files`

---

## 3) Files changed (and rationale per file)

- `backend/app/strategies/schemas.py` — New: Pydantic models for preset API (~38 LOC)
- `backend/app/strategies/router.py` — New: FastAPI router with GET /presets and POST /from-preset, PRESETS_REGISTRY (~96 LOC)
- `backend/app/strategies/presets/__init__.py` — Updated: export all three generators (grid, dca, btd)
- `backend/tests/test_presets_api.py` — New: 7 pytest tests covering list, generate, and error cases (~87 LOC)
- Cherry-picked: `grid.py` (2d2f707), `btd.py` (25b5b18), `dca_bot.py` (45355d3)

---

## 4) Tests run & results

- **Commands run:**
  - `cd backend && uv run python -m pytest tests/test_presets_api.py -q` — 7 passed
  - `cd backend && uv run python -m mypy app/strategies/router.py app/strategies/schemas.py --ignore-missing-imports` — Success

---

## 5) Data & sample evidence

- All data synthetic, passed as request parameters
- DCA: `{interval_hours: 4, amount_per_buy: 50, max_buys: 10}` → 2 rules
- Grid: `{lower_price: 100, upper_price: 200, num_grids: 4, amount_per_grid: 10}` → 5 rules
- BTD: `{dip_pct: 5, recovery_pct: 2, take_profit_pct: 10}` → 3 rules

---

## 6) Risk assessment & mitigations

- **Risk:** grid.py/btd.py not on branch — **Severity:** low — **Mitigation:** cherry-picked from commits
- **Risk:** int/float type coercion — **Severity:** low — **Mitigation:** registry-driven casting

---

## 7) Backwards compatibility / migration notes

- Additive API only, fully backward compatible. No DB migrations.

---

## 8) Performance considerations

- Stateless, in-memory computation. <1ms per request.

---

## 9) Security & safety checks

- forbidden paths touched: `no`
- external/broker sdk usage: `no`
- secrets touched: `no`

---

## 10) Open questions & follow-ups

1. Router not yet registered in main FastAPI app — integration out of scope for this task.

---

## 11) Short changelog

- (pending) — feat(marketpulse-task-2026-04-01-0011): preset bots API with list and generate endpoints

---

## 12) Final verdict (developer self-check)

- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `validate`

# Rationale for `marketpulse-task-2026-04-01-0001`

**author:** coder-agent (MarketPulse Coder)
**branch:** task/marketpulse-task-2026-04-01-0001-implementation
**date:** 2026-04-01

---

## 1) One-line summary
Strategy rule data model as Pydantic v2 schemas with in-memory CRUD store — foundation for v5 strategy builder.

---

## 2) Mapping to acceptance criteria

- **Criteria:** StrategyCondition validates indicator names against allowed literals
- **Status:** `pass`
- **Evidence:** Pydantic Literal type enforces allowed indicator names; test_valid_rule_creation verifies

- **Criteria:** StrategyCondition with operator='between' requires value_upper
- **Status:** `pass`
- **Evidence:** model_validator raises ValidationError; test_between_operator_requires_upper confirms

- **Criteria:** StrategyAction constrains action to buy/sell/hold with weight 0-2
- **Status:** `pass`
- **Evidence:** Literal type + Field(ge=0, le=2) enforced by Pydantic

- **Criteria:** Strategy requires at least 1 rule (min_length=1)
- **Status:** `pass`
- **Evidence:** test_strategy_requires_at_least_one_rule confirms ValidationError on empty list

- **Criteria:** Strategy.signal_actions returns set of unique action types from rules
- **Status:** `pass`
- **Evidence:** test_strategy_signal_actions_property verifies {buy, sell} from 3 rules

- **Criteria:** StrategyStore.add stores and returns strategy with its id
- **Status:** `pass`
- **Evidence:** test_store_add_and_get

- **Criteria:** StrategyStore.get returns None for unknown id
- **Status:** `pass`
- **Evidence:** test_store_delete (get after delete returns None)

- **Criteria:** StrategyStore.delete returns True if found, False otherwise
- **Status:** `pass`
- **Evidence:** test_store_delete + test_store_delete_nonexistent

- **Criteria:** All 11 tests pass
- **Status:** `pass`
- **Evidence:** pytest output: 11 passed in 0.04s

- **Criteria:** mypy reports no errors
- **Status:** `pass`
- **Evidence:** mypy output: Success: no issues found in 1 source file

---

## 3) Files changed (and rationale per file)
- `backend/app/strategies/__init__.py` — empty init for new package
- `backend/app/strategies/models.py` — Pydantic v2 models (StrategyCondition, StrategyAction, StrategyRule, Strategy) + StrategyStore
- `backend/tests/test_strategy_rules.py` — 11 unit tests covering model validation and store CRUD
- `rationale.md` — this file

---

## 4) Tests run & results
- `cd backend && uv run python -m pytest tests/test_strategy_rules.py -q` → 11 passed
- `cd backend && uv run python -m mypy app/strategies/models.py --ignore-missing-imports` → Success, no issues

---

## 5) Data & sample evidence
- No external data. All tests use inline synthetic data.

---

## 6) Risk assessment & mitigations
- **Risk:** Naming conflict — `strategies/` (plural) vs existing `strategy/` (singular) — **Severity:** low — **Mitigation:** Different directory names with clear separation of concerns (user-defined vs built-in)

---

## 7) Backwards compatibility / migration notes
- New files only, no existing code modified. Fully backward compatible.

---

## 8) Performance considerations
- No performance impact. Pure data models and dict-backed store.

---

## 9) Security & safety checks
- forbidden paths touched: `no`
- external/broker sdk usage: `no`
- secrets touched: `no`
- API key logged: `no`

---

## 10) Open questions & follow-ups
1. Strategy CRUD API endpoints (next task).
2. Strategy evaluation logic (separate task).
3. Preset strategies definition.

---

## 11) Short changelog
- feat(marketpulse-task-2026-04-01-0001): strategy rule Pydantic models + in-memory store

---

## 12) Final verdict (developer self-check)
- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `validate`

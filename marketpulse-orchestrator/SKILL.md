---
name: marketpulse-orchestrator
description: orchestrate, decompose and validate engineering task briefs for marketpulse ai. use when converting product/feature requests into developer-ready task specs, verifying coder outputs against the spec, and enforcing product guardrails (deterministic core, explainability, paper-trading-only, caution-first).
---

# MarketPulse Orchestrator — SKILL

## Quick summary / when to use
Use this skill when you need a repeatable, auditable agent that:
- Konwertuje product-level request (feature / bug / improvement) dla **MarketPulse AI** na developer-ready task spec.
- Generuje priorytetowy, dependency-aware plan implementacji z jasnymi acceptance criteria.
- Weryfikuje odpowiedź agenta-codera (diff, testy, logi) względem oryginalnego task spec i wydaje verdict (`approve|revise|reject|ask_human`).
- Egzekwuje produktowe guardrails: **grounded**, **deterministic core**, **AI = explainability**, **paper-trading-only**, **caution-first**, audytowalność.

**Nie** używać tej umiejętności do otwartego brainstormingu ani do implementowania kodu produkcyjnego dla real tradingu.

---

## Behavior & constraints
- **Strukturalny output**: preferuj JSON-first (maszyna) + krótka wersja human-readable.
- **Audit trail**: każde wyjście musi zawierać `task_id`, `timestamp`, `created_by` (agent id).
- **Enforce guardrails**: natychmiast flaguj żądania naruszające filozofię (np. deploy do real tradingu).
- **Deterministyczne specyfikacje**: gdzie możliwe — numery, progi, polecenia CLI.
- **Scope control**: rekomenduj małe, ograniczone taski (zalecenie: ≤ 3 pliki, ≤ 300 LOC) albo obowiązkowe uzasadnienie większego scope.
- **Testability mandatory**: każda implementacja wymaga automatycznych testów (unit/integration) i poleceń testowych.
- **Odmowa wykonywania**: agent nie pisze kodu ani nie uruchamia deployów — tylko specyfikacje i walidacje.

---

## Core capabilities

### 1. Feature decomposition
Rozbij zadanie na: `goal`, `in_scope`, `out_of_scope`, `subtasks`, `dependencies`, `estimated_complexity`.  
Dla każdego subtaska podaj: `owner`, `files_likely_touched`, `data_needs`, `tools`, `expected_tests`, `acceptance_criteria`.

### 2. Spec generation (developer-ready)
Generuj JSON contract i krótkie streszczenie. JSON musi zawierać m.in.:
- `acceptance_criteria[]`, `required_checks[]`, `allowed_paths[]`, `forbidden_paths[]`,
- `max_iterations`, `stop_conditions[]`.

### 3. Risk & dependency analysis
Wypisz zależności, ocenę ryzyka (`low|medium|high`) z uzasadnieniem oraz mitigacje. Zaznacz, kiedy potrzebne jest `ask_human` przed startem.

### 4. Validation / verification
Na podstawie: `git_diff`, `commit_sha`, `test_logs`, `lint_logs`, `rationale.md` — zwróć `verdict` z dowodem (diff lines, logs). Dla `revise` podaj priorytety napraw.

### 5. Scope & safety enforcement
Egzekwuj `forbidden_paths`, `paper-trading-only`, zakaz deployów/secrets. Jeśli task próbuje obejść zasady — `ask_human`.

---

## Output formats

### Task spec JSON (canonical)
Agent **zawsze** zwraca JSON task spec w tym kształcie (skrót — wymagana struktura):

```json
{
  "task_id":"string",
  "created_at":"ISO8601",
  "created_by":"marketpulse-orchestrator-v1",
  "title":"string",
  "goal":"string",
  "in_scope":["..."],
  "out_of_scope":["..."],
  "subtasks":[
    {
      "id":"string",
      "title":"string",
      "description":"string",
      "owner":"string",
      "files_expected":["..."],
      "required_checks":["..."],
      "acceptance_criteria":["..."],
      "max_change_loc":300,
      "max_files_changed":3,
      "risks":[{"type":"", "severity":"low|medium|high", "explanation":""}]
    }
  ],
  "dependencies":["..."],
  "priority":"low|medium|high",
  "estimated_effort":"S|M|L",
  "forbidden_paths":[".env","infra/","secrets/"],
  "stop_conditions":["tests_fail_3_iterations"],
  "max_iterations":5,
  "authorization":{
    "level":"auto_approve|human_review",
    "deploy_allowed":false,
    "allowed_actions":["read_file","write_file","git_commit","run_tests","lint_check"],
    "forbidden_actions":["deploy","access_secrets","call_broker_api"],
    "audit_required":true,
    "max_iterations":5
  }
}
```

### Validation verdict JSON
```json
{
  "task_id":"string",
  "verdict":"approve|revise|reject|ask_human",
  "checks":{
    "commit_message_has_task_id":true,
    "files_match_expected":true,
    "forbidden_paths_clean":true,
    "required_checks_pass":true,
    "rationale_present":true,
    "acceptance_criteria_mapped":true
  },
  "issues":[{"area":"string","severity":"low|med|high","description":"string"}],
  "fix_priority":["string"]
}
```

---

## Required tools / connectors

| Tool | Used by | Purpose |
|------|---------|---------|
| `git` | All agents | Branch, commit, diff, log |
| `pytest` | Coder, Validator | Run unit + integration tests |
| `mypy` / `pyright` | Coder, Validator | Static type checking |
| `ruff` | Coder | Fast Python linter |
| `flask` | Coder | API framework (test client) |
| `jq` | Validator | Parse JSON outputs |
| `read_file` / `write_file` | Coder | File I/O |
| `time_series_preview` | Coder (future) | Preview financial data |

---

## Decision rules

| Condition | Orchestrator action |
|-----------|---------------------|
| All acceptance criteria pass + tests green | `approve` — forward to validator |
| Tests pass but criteria partial | `revise` — return priority fix list |
| Tests fail ≤ 3 iterations | `revise` — Coder retries |
| Tests fail > 3 iterations | `ask_human` — escalate |
| Forbidden paths touched | `reject` + `ask_human` immediately |
| Secrets detected in diff | `reject` + `ask_human` immediately |
| Deploy attempted | `reject` + `ask_human` immediately |
| Broker SDK imported | `reject` + `ask_human` immediately |
| authorization.level = human_review, no approval | `ask_human` before Coder starts |
| Scope exceeds max_files/max_loc | `revise` — Coder must justify or split |

---

## References

- `references/rationale_template.md` — 12-section rationale template
- `references/acceptance_patterns.md` — binary testable acceptance criteria patterns
- `references/cli_checklist.md` — pre-merge validation checklist
- `references/authorization.md` — authorization schema and examples
- `prompts/orchestrator_to_coder.md` — task handoff prompt
- `prompts/orchestrator_to_validator.md` — validation request prompt
- `prompts/coder_to_orchestrator.md` — result report prompt
- `prompts/marketpulse_coder.md` — full Coder agent prompt

---

## Integrator notes (CI / operator)

### Branch conventions
- Orchestrator creates branch: `task/<task_id>-short-description`
- Coder commits on that branch with `task_id` in every message
- Validator runs on the branch diff vs base_ref (usually `main` or `master`)

### CI hook integration
1. On PR open/update: run `python validator.py --task-spec task_store/<task_id>.json --repo . --base main`
2. Validator returns verdict JSON — CI posts as PR comment
3. If verdict = `approve`: auto-merge allowed (with human review for `human_review` tasks)
4. If verdict = `revise`: block merge, post fix_priority list as comment

### Operator endpoint (future)
- `POST /api/orchestrator/submit-task` — accepts task_spec JSON, queues for Coder
- `GET /api/orchestrator/task/<id>/status` — returns current verdict/state
- `POST /api/orchestrator/task/<id>/approve` — human approval for `human_review` tasks
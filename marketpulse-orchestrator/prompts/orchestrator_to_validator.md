---
title: "Orchestrator -> Validator Handoff"
summary: "Orchestrator sends task_spec + coder_result to Validator for automated verification. Validator returns verdict JSON."
---

# Orchestrator -> Validator — Validation Request

## Input
Orchestrator sends:

```json
{
  "task_spec_path": "task_store/task_example.json",
  "repo_path": "/path/to/repo",
  "base_ref": "master",
  "task_branch": "task/<task_id>-short-description",
  "coder_result": {
    "task_id": "string",
    "commit_sha": "string",
    "files_changed": ["string"],
    "tests": {"passed": true, "summary": "string"},
    "acceptance_criteria_results": [{"criteria":"...","status":"pass","evidence":"..."}]
  }
}
```

## Validator Responsibilities
1. **Load task_spec** from `task_spec_path`.
2. **Verify commit messages** contain `task_id` in all commits on task branch.
3. **Compare files changed** vs `files_expected` (prefix matching).
4. **Check forbidden_paths** — no files in `.env`, `infra/`, `secrets/` touched.
5. **Run required_checks** — execute each command, capture exit code + stdout (truncate 2000 chars).
6. **Map acceptance_criteria** — for each criterion, check if matching test passed.
7. **Check rationale.md** — exists, has sections, maps criteria to evidence.
8. **Produce verdict** — `approve`, `revise`, or `reject`.

## Expected Output (JSON-first)

```json
{
  "task_id": "string",
  "verdict": "approve|revise|reject|ask_human",
  "checks": {
    "commit_message_has_task_id": true,
    "files_match_expected": true,
    "forbidden_paths_clean": true,
    "required_checks_pass": true,
    "rationale_present": true,
    "acceptance_criteria_mapped": true
  },
  "required_checks_results": [
    {"cmd": "string", "exit_code": 0, "stdout_excerpt": "string"}
  ],
  "issues": [
    {"area": "string", "severity": "low|med|high", "description": "string"}
  ],
  "fix_priority": ["description of fix 1"],
  "notes": "optional"
}
```

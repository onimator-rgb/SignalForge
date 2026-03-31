---
title: "Orchestrator -> Coder Task Handoff"
summary: "JSON-first task spec delivered from Orchestrator to Coder agent. Coder must return structured JSON result + human summary."
---

# Orchestrator -> Coder — Task Handoff Prompt

## Input (JSON-first)
Orchestrator sends the following JSON to Coder:

```json
{
  "task_spec": {
    "task_id": "marketpulse-task-YYYYMMDD-NNNN",
    "title": "string",
    "goal": "string",
    "subtasks": [
      {
        "id": "s1",
        "title": "string",
        "description": "detailed work description",
        "files_expected": ["src/...", "tests/..."],
        "required_checks": ["pytest ...", "mypy ..."],
        "acceptance_criteria": ["binary testable criterion"],
        "max_change_loc": 300,
        "max_files_changed": 6
      }
    ],
    "forbidden_paths": [".env", "infra/", "secrets/"],
    "stop_conditions": ["tests_fail_3_iterations", "touch_secrets"],
    "max_iterations": 5,
    "authorization": {
      "level": "auto_approve|human_review",
      "deploy_allowed": false,
      "audit_required": true
    }
  },
  "repo_path": "/path/to/repo",
  "base_ref": "main",
  "branch": "task/<task_id>-short-description"
}
```

## Hard Rules for Coder
1. **forbidden_paths** — NEVER modify. If required, stop and set `next_recommended_step: "ask_human"`.
2. **max_files_changed / max_change_loc** — do not exceed without justification in rationale.md.
3. **commit messages** — every commit MUST contain `task_id`.
4. **branch format** — `task/<task_id>-short-description`.
5. **rationale.md** — MUST be present, following `references/rationale_template.md`.
6. **no deploys, no secrets, no real trading** — paper-trading-only, demo auth only.
7. **stop_conditions** — if tests fail 3 iterations, stop and report.

## Expected Output from Coder
Coder returns **JSON first** (no text before), then 3-6 sentence human summary:

```json
{
  "task_id": "string",
  "branch": "string",
  "commit_sha": "string",
  "files_changed": ["string"],
  "commands_run": [{"cmd": "string", "exit_code": 0, "stdout": "string"}],
  "tests": {"passed": true, "summary": "string", "failed_tests": []},
  "lint": {"passed": true, "output": "string"},
  "acceptance_criteria_results": [
    {"criteria": "string", "status": "pass|fail|partial", "evidence": "string"}
  ],
  "rationale_path": "rationale.md",
  "issues": [{"path": "string", "severity": "low|med|high", "description": "string"}],
  "next_recommended_step": "approve|revise|ask_human",
  "notes": "optional"
}
```

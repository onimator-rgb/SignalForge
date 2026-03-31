---
title: "Coder -> Orchestrator Result Report"
summary: "Structured JSON result that Coder sends back to Orchestrator after completing a task."
---

# Coder -> Orchestrator — Result Report

## When to Send
After completing all subtasks, hitting a stop_condition, or encountering a blocker.

## Report Format (JSON-first, then human summary)

```json
{
  "task_id": "marketpulse-task-YYYYMMDD-NNNN",
  "branch": "task/<task_id>-short-description",
  "commit_sha": "final commit SHA",
  "files_changed": ["list of all files modified/created"],
  "commands_run": [
    {"cmd": "pytest tests/... -q", "exit_code": 0, "stdout": "14 passed"}
  ],
  "tests": {
    "passed": true,
    "summary": "14/14 passed",
    "failed_tests": []
  },
  "lint": {
    "passed": true,
    "output": "mypy: Success"
  },
  "acceptance_criteria_results": [
    {
      "criteria": "exact text from task_spec",
      "status": "pass|fail|partial",
      "evidence": "test name + PASSED, or diff reference"
    }
  ],
  "rationale_path": "rationale.md",
  "issues": [
    {"path": "string", "severity": "low|med|high", "description": "string"}
  ],
  "next_recommended_step": "approve|revise|ask_human",
  "notes": "optional"
}
```

## After JSON
3-6 sentence human summary: what was implemented, test results, open questions.

## Orchestrator Decision Matrix
| Coder says | Tests | Criteria | Orchestrator action |
|------------|-------|----------|---------------------|
| approve    | pass  | all pass | validator.py -> merge |
| approve    | pass  | partial  | validator.py -> revise |
| revise     | fail  | any      | Return fix list, iteration++ |
| ask_human  | any   | any      | Escalate with full context |

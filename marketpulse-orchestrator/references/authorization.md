---
title: Authorization Schema
summary: Authorization/auto-approve schema for MarketPulse agents. Defines what actions are allowed, forbidden, and when human approval is needed.
---

# Authorization Schema — MarketPulse Orchestrator

## Schema

```json
{
  "authorization": {
    "level": "auto_approve | human_review",
    "deploy_allowed": false,
    "allowed_actions": [
      "read_file",
      "write_file",
      "git_commit",
      "run_tests",
      "lint_check"
    ],
    "forbidden_actions": [
      "deploy",
      "access_secrets",
      "call_broker_api",
      "push_to_production",
      "modify_infra"
    ],
    "audit_required": true,
    "max_iterations": 5
  }
}
```

## Levels

| Level | Behavior |
|-------|----------|
| `auto_approve` | Coder proceeds autonomously. Validator runs post-hoc. |
| `human_review` | Coder stops before commit and waits for explicit human approval. |

## Rules

1. **deploy_allowed** is ALWAYS `false` in MarketPulse. No agent may deploy.
2. **forbidden_actions** are hard blocks — agent must stop and set `next_recommended_step: "ask_human"`.
3. **audit_required** means every action is logged in rationale.md and commit history.
4. **max_iterations** — if Coder exceeds this count without passing checks, escalate to human.

## When to Escalate (ask_human)

- Forbidden path would need modification
- Secrets access required
- Deploy requested
- Broker API needed
- Tests fail after max_iterations
- Scope exceeds max_files_changed or max_change_loc without justification
- authorization.level = human_review and no approval received

## Audit Trail

Every task produces:
1. **Git commits** with task_id in message
2. **rationale.md** mapping decisions to evidence
3. **Validator JSON** with verdict and check results
4. **Branch** named `task/<task_id>-*` for traceability

## Example: Auto-approve Task

```json
{
  "task_id": "marketpulse-task-2026-03-31-0001",
  "authorization": {
    "level": "auto_approve",
    "deploy_allowed": false,
    "allowed_actions": ["read_file", "write_file", "git_commit", "run_tests", "lint_check"],
    "forbidden_actions": ["deploy", "access_secrets", "call_broker_api"],
    "audit_required": true,
    "max_iterations": 5
  }
}
```

## Example: Human-review Task

```json
{
  "task_id": "marketpulse-task-2026-04-01-0001",
  "authorization": {
    "level": "human_review",
    "deploy_allowed": false,
    "allowed_actions": ["read_file", "write_file", "run_tests"],
    "forbidden_actions": ["deploy", "access_secrets", "call_broker_api", "git_commit"],
    "audit_required": true,
    "max_iterations": 3
  }
}
```

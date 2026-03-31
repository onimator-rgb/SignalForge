---
title: CLI Checklist
summary: Deterministic checklist for validating coder output before Orchestrator verdict. Used by validator.py and human reviewers.
---

# CLI Checklist — MarketPulse Orchestrator

## Pre-merge validation (run in order)

### 1. Branch & commit conventions
```bash
# Verify branch name matches task/<task_id>-*
git rev-parse --abbrev-ref HEAD | grep -E '^task/marketpulse-task-[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{4}'

# Verify all commits contain task_id
git log main..HEAD --oneline | grep -c '<task_id>'
```

### 2. Files changed vs files_expected
```bash
# List changed files
git diff --name-only main..HEAD

# Compare against task_spec.subtasks[].files_expected (prefix match)
# Extra files require rationale in rationale.md
```

### 3. Forbidden paths untouched
```bash
# Must return 0 results
git diff --name-only main..HEAD | grep -E '^(\.env|infra/|secrets/)'
```

### 4. LOC within limits
```bash
# Count added lines (should be <= max_change_loc)
git diff main..HEAD --stat | tail -1
```

### 5. Required checks pass
```bash
pytest tests/test_anomalies_api.py -q
python -m mypy src/ --ignore-missing-imports
# Add project-specific lint: ruff check src/ tests/
```

### 6. Rationale.md present and complete
```bash
# File exists
test -f rationale.md && echo "OK" || echo "MISSING"

# Contains all 12 sections
grep -c '## [0-9]' rationale.md  # should be >= 12
```

### 7. Acceptance criteria mapped
```bash
# Each criterion from task_spec should appear in rationale.md section 2
# with status: pass|fail|partial and evidence
grep -c 'Status.*pass\|Status.*fail\|Status.*partial' rationale.md
```

### 8. Security checks
```bash
# No secrets in diff
git diff main..HEAD | grep -iE '(api_key|secret|password|token)' | grep -v 'DEMO_TOKEN' | grep -v '#'

# No broker SDK imports
git diff main..HEAD | grep -iE '(import.*broker|from.*broker|alpaca|ibkr|binance\.client)'

# No deploy commands
git diff main..HEAD | grep -iE '(kubectl|docker push|helm install|terraform apply)'
```

### 9. Test coverage (optional)
```bash
pytest --cov=src --cov-report=term-missing tests/ -q
```

### 10. Final verdict decision
| Condition | Verdict |
|-----------|---------|
| All checks pass, all criteria pass | `approve` |
| Minor issues, tests pass | `approve` with notes |
| Tests fail or criteria partial | `revise` with priority list |
| Forbidden paths touched or secrets found | `reject` + `ask_human` |

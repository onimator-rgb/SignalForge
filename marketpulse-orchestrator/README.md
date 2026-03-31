# MarketPulse Orchestrator

Task decomposition, validation, and agent coordination for MarketPulse AI.

## Structure

```
marketpulse-orchestrator/
  SKILL.md                          # Orchestrator capability definition
  validator.py                      # Automated task validation
  README.md                         # This file
  task_store/
    task_example.json               # Example task spec
  prompts/
    orchestrator_to_coder.md        # Task handoff prompt
    orchestrator_to_validator.md    # Validation request prompt
    coder_to_orchestrator.md        # Result report prompt
    marketpulse_coder.md            # Full Agent 2 (Coder) prompt
  references/
    rationale_template.md           # 12-section rationale template
    acceptance_patterns.md          # Binary testable criteria patterns
    cli_checklist.md                # Pre-merge validation checklist
    authorization.md                # Authorization schema
  workers/
    coder_worker.py                 # Coder agent worker (CLI)
    Dockerfile                      # Container for workers
    docker-compose.yml              # Run coder + validator together
```

## Quick Start

### Run Coder Worker locally
```bash
python marketpulse-orchestrator/workers/coder_worker.py \
  --task marketpulse-orchestrator/task_store/task_example.json \
  --repo /path/to/target/repo \
  --base main
```

### Run Validator locally
```bash
python marketpulse-orchestrator/validator.py \
  --task-spec marketpulse-orchestrator/task_store/task_example.json \
  --repo /path/to/target/repo \
  --base main
```

### Run E2E with Docker
```bash
cd marketpulse-orchestrator/workers
docker-compose up --build
```

### Run tests in target repo
```bash
python -m pytest tests/ -v
python -m mypy src/ --ignore-missing-imports
python -m ruff check src/ tests/
```

## Pipeline Flow

```
1. Orchestrator generates task_spec JSON
2. Coder Worker receives task_spec, creates branch, implements changes
3. Coder runs required_checks (pytest, mypy), creates rationale.md
4. Coder commits with task_id in message, exports JSON report
5. Validator reads task_spec + repo, verifies all checks
6. Validator returns verdict: approve | revise | reject
```

## Branch & Commit Conventions

- **Branch**: `task/<task_id>-short-description`
- **Commits**: must contain `task_id` in message
- **rationale.md**: required in repo root for every task

## Security Rules

- No deploys, no real broker APIs, no secrets access
- Paper-trading only — all data is synthetic/demo
- forbidden_paths: `.env`, `infra/`, `secrets/`
- Demo auth only: `Bearer DEMO_TOKEN`

## Required Tools

| Tool | Purpose |
|------|---------|
| Python 3.9+ | Runtime |
| pytest | Tests |
| mypy | Type checking |
| ruff | Linting (optional) |
| flask | API framework |
| git | Version control |

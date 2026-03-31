---
title: Acceptance Patterns
summary: Zbiór powtarzalnych, binarnych i testowalnych wzorców acceptance criteria oraz przykładowe polecenia CLI do walidacji. Użyć przez Orchestrator przy generowaniu task speców.
---

# Acceptance Patterns — MarketPulse Orchestrator

> Zasady:  
> - Kryteria muszą być **binary** (pass/fail) i **ewidencjonowalne** (test command / evidence).  
> - Dla każdych kryteriów podaj dokładne polecenie do uruchomienia testu (CLI) i przykładową fixture/data.  
> - Dla zmian w scoringu wymagaj **rationale** łączącej sygnały z wynikiem.

---

## 1. API / Endpoint patterns

### A. Standard JSON endpoint
**Pattern:**  
`endpoint {METHOD} {URL} returns 200 and JSON keys {<keys[]>} for valid demo token`

**Acceptance Criteria example:**
- `GET /api/watchlist/{id}/anomalies returns 200 and JSON with keys ["assets","anomalies","last_updated"] when called with valid demo token`

**Test command:**  
```bash
curl -s -H "Authorization: Bearer DEMO_TOKEN" "http://localhost:8080/api/watchlist/123/anomalies" | jq 'keys'
# or
pytest tests/test_api_watchlist_anomalies.py::test_anomalies_endpoint --maxfail=1 -q
```

### B. Error handling endpoint
**Pattern:**
`endpoint {METHOD} {URL} returns 401 when called without auth token`

**Test command:**
```bash
pytest tests/test_api_watchlist_anomalies.py::test_returns_401_without_token -q
```

---

## 2. Anomaly Detection patterns

### A. Filtering by severity threshold
**Pattern:**
`filter returns only anomalies with severity >= {threshold}`

**Acceptance Criteria example:**
- `filter_unresolved returns only records with severity >= 0.5`

**Test command:**
```bash
pytest tests/test_anomalies_api.py::TestFilterUnresolved::test_filters_by_severity -q
```

### B. Time window filtering
**Pattern:**
`filter excludes records older than {hours}h from reference time`

**Test command:**
```bash
pytest tests/test_anomalies_api.py::TestFilterUnresolved::test_excludes_older_than_24h -q
```

### C. Deduplication within window
**Pattern:**
`two identical anomalies (same asset+type) within {minutes} minutes produce single record with occurrences >= 2`

**Test command:**
```bash
pytest tests/test_anomalies_api.py::TestDeduplicate::test_merges_same_asset_type_within_window -q
```

### D. Resolved exclusion
**Pattern:**
`filter excludes anomalies where resolved=true`

**Test command:**
```bash
pytest tests/test_anomalies_api.py::TestFilterUnresolved::test_excludes_resolved -q
```

---

## 3. Scoring / Explainability patterns

### A. Score contains rationale
**Pattern:**
`scoring response includes "rationale" field explaining signal-to-score mapping`

**Acceptance Criteria example:**
- `POST /api/score returns JSON with keys ["score","rationale","signals"] and rationale is non-empty string`

**Test command:**
```bash
pytest tests/test_scoring.py::test_score_has_rationale -q
```

### B. Score determinism
**Pattern:**
`same input produces same score across 3 consecutive calls`

**Test command:**
```bash
pytest tests/test_scoring.py::test_deterministic_score -q
```

---

## 4. Demo Portfolio patterns

### A. Portfolio returns valid structure
**Pattern:**
`GET /api/portfolio/{id} returns JSON with keys ["positions","total_value","currency","last_updated"]`

**Test command:**
```bash
pytest tests/test_portfolio.py::test_portfolio_structure -q
```

### B. Paper-trading only
**Pattern:**
`portfolio endpoint never calls real broker API — verified by mock assertion`

**Test command:**
```bash
pytest tests/test_portfolio.py::test_no_real_broker_calls -q
```

---

## 5. Data Ingestion patterns

### A. Fixture loading
**Pattern:**
`ingestion service loads synthetic fixture and returns {N} records with required schema`

**Acceptance Criteria example:**
- `load_fixture("synthetic_price_spike.json") returns list of dicts with keys ["id","asset","type","severity","timestamp"]`

**Test command:**
```bash
pytest tests/test_ingestion.py::test_fixture_schema -q
```

### B. Timestamp parsing
**Pattern:**
`ISO-8601 timestamps with Z suffix are parsed as UTC datetime`

**Test command:**
```bash
pytest tests/test_anomalies_api.py -k "timestamp" -q
```

---

## 6. CI / Lint / Typecheck patterns

### A. All tests pass
**Pattern:**
`pytest {test_path} exits with code 0 and reports 0 failures`

**Test command:**
```bash
pytest tests/ -q --tb=short
```

### B. Type check clean
**Pattern:**
`mypy {src_path} --ignore-missing-imports exits with code 0`

**Test command:**
```bash
python -m mypy src/ --ignore-missing-imports
```

### C. Lint clean
**Pattern:**
`ruff check {paths} exits with code 0`

**Test command:**
```bash
python -m ruff check src/ tests/
```

---

## 7. Security Guardrails patterns

### A. No forbidden paths in diff
**Pattern:**
`git diff --name-only base..head | grep -E "^(\.env|infra/|secrets/)" returns 0 matches`

**Test command:**
```bash
git diff --name-only main..HEAD | grep -cE '^(\.env|infra/|secrets/)' | grep '^0$'
```

### B. No secrets in code
**Pattern:**
`diff contains no hardcoded API keys, passwords, or tokens (except DEMO_TOKEN)`

**Test command:**
```bash
git diff main..HEAD | grep -iE '(api_key|secret_key|password)' | grep -v DEMO_TOKEN | wc -l
# must be 0
```

### C. No broker SDK imports
**Pattern:**
`diff contains no imports of real trading SDKs`

**Test command:**
```bash
git diff main..HEAD | grep -iE '(import.*alpaca|from.*ibkr|import.*binance)' | wc -l
# must be 0
```

### D. No deploy commands
**Pattern:**
`diff contains no deployment commands`

**Test command:**
```bash
git diff main..HEAD | grep -iE '(kubectl apply|docker push|terraform apply|helm install)' | wc -l
# must be 0
```

### E. Rationale.md present
**Pattern:**
`rationale.md exists in repo root and contains >= 12 section headers`

**Test command:**
```bash
test -f rationale.md && grep -c '^## [0-9]' rationale.md
# must be >= 12
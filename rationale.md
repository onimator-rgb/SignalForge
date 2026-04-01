# Rationale for `marketpulse-task-2026-04-01-0005`

**author:** coder-worker (MarketPulse Coder)
**branch:** task/marketpulse-task-2026-04-01-0005-implementation
**date:** 2026-04-01

---

## 1) One-line summary
Added 4h and 1d ingestion intervals to the asyncio scheduler for both crypto and stock asset classes.

---

## 2) Mapping to acceptance criteria

- **Criteria:** start_scheduler() creates 6 asyncio tasks (2 existing 1h + 2 new 4h + 2 new 1d)
- **Status:** `pass`
- **Evidence:** test_start_scheduler_creates_six_tasks verifies len(_tasks) == 6

- **Criteria:** 4h jobs use interval_seconds=14400 (4*3600)
- **Status:** `pass`
- **Evidence:** test_4h_jobs_use_correct_interval checks interval_sec == 14400

- **Criteria:** 1d jobs use interval_seconds=86400 (24*3600)
- **Status:** `pass`
- **Evidence:** test_1d_jobs_use_correct_interval checks interval_sec == 86400

- **Criteria:** get_scheduler_status() reports all 6 jobs
- **Status:** `pass`
- **Evidence:** test_get_scheduler_status_reports_all_jobs verifies all 6 job names in status

- **Criteria:** stop_scheduler() cancels all 6 tasks
- **Status:** `pass`
- **Evidence:** test_stop_scheduler_cancels_all_tasks verifies cancel() called on all 6 and list cleared

- **Criteria:** All tests pass with pytest
- **Status:** `pass`
- **Evidence:** 7 passed in 0.08s

- **Criteria:** mypy passes with no errors
- **Status:** `pass`
- **Evidence:** Zero mypy errors in app/scheduler.py (pre-existing errors in other files are unrelated)

---

## 3) Files changed

| File | Action | LOC changed |
|------|--------|-------------|
| backend/app/scheduler.py | modified | ~30 |
| backend/tests/test_scheduler_intervals.py | created | ~170 |

---

## 4) Approach

Reused the existing `_periodic_loop` pattern unchanged. Added 4 new `asyncio.create_task` calls in `start_scheduler()` for crypto_4h, stock_4h, crypto_1d, stock_1d with appropriate interval_seconds values. Updated the log message to list all 6 jobs.

---

## 5) Risks & mitigations

- **Risk:** Additional long-running tasks consuming resources
- **Mitigation:** Uses same lightweight asyncio pattern; no new threads or processes
- **Severity:** low

---

## 6) Open questions

None — this is a straightforward extension of an existing pattern.

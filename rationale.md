# Rationale — marketpulse-task-2026-04-01-0013

## 1. Task Summary
Add multi-timeframe indicator calculation: a service function that concurrently fetches indicators across multiple intervals, a response schema, and a REST endpoint.

## 2. Approach
Reused the existing `get_indicators()` function, wrapping concurrent calls via `asyncio.gather()`. Added a new Pydantic schema `MultiTimeframeIndicators` and a FastAPI endpoint at `GET /api/v1/assets/{asset_id}/indicators/mtf`.

## 3. Files Changed
- `backend/app/indicators/schemas.py` — added `MultiTimeframeIndicators` model
- `backend/app/indicators/service.py` — added `get_multi_timeframe_indicators()` with `asyncio.gather`
- `backend/app/indicators/router.py` — added MTF endpoint with interval validation
- `backend/tests/test_mtf_indicators.py` — 5 comprehensive tests (all mock-based)

## 4. Design Decisions
- Default intervals `['5m', '1h', '4h', '1d']` match common trading timeframes
- Comma-separated query param for intervals (simple, REST-friendly)
- Allowed intervals whitelist prevents invalid DB queries
- `asyncio.gather` for concurrent execution (no sequential bottleneck)

## 5. Risks & Mitigations
- **DB load**: Multiple concurrent queries per request. Mitigated by reusing existing connection pool and limited interval whitelist.
- **Integration**: Minimal risk — reuses battle-tested `get_indicators()`.

## 6. Testing
5 tests covering: default intervals, custom intervals, None handling, concurrency verification, schema serialization. All mock-based, no DB required.

## 7. Acceptance Criteria Status
All acceptance criteria met for subtasks s1, s2, s3.

## 8. Pre-existing Issues
3 mypy errors exist in service.py (lines 100, 183, 184) unrelated to this change — they predate this task.

## 9. Dependencies
Existing: `get_indicators()`, `IndicatorSnapshot`, `Asset` model, `get_db`.

## 10. Security
No secrets accessed, no broker APIs called, no deployment. Paper-trading only.

## 11. Performance
Concurrent execution via `asyncio.gather` — total latency ≈ max(single interval latency) rather than sum.

## 12. Next Steps
`next_recommended_step: "approve"` — all tests pass, code is ready for review.

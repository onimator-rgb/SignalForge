# Rationale — marketpulse-task-2026-04-01-0023

## 1. Task Summary
Replace compact entry-decision badges in PortfolioView with a detailed, filterable table section showing full decision context.

## 2. Approach
- Added `EntryDecision` TypeScript interface matching API response shape (10 fields).
- Replaced badge row with a full table: Time, Symbol, Status (color-coded), Stage, Reasons, Regime, Profile.
- Added filter tabs (All/Allowed/Blocked/Pending) that re-fetch from the API with `?status=` param.
- Clickable rows expand to show `reason_text` in a sub-row.
- "Load more" button fetches next page via `?offset=` when 20+ results exist.

## 3. Files Changed
| File | Change |
|------|--------|
| `frontend/src/types/api.ts` | Added `EntryDecision` interface |
| `frontend/src/views/PortfolioView.vue` | Replaced badges with filterable table panel |

## 4. Design Decisions
- Reused existing table styling from closed-positions section for consistency.
- Status color scheme: green=allowed, red=blocked, yellow=pending, gray=expired.
- Filter tabs use pill-button pattern with `bg-blue-600` active state.
- Empty state shows contextual message including active filter name.

## 5. API Integration
- Uses existing `GET /api/v1/portfolio/entry-decisions` endpoint.
- Query params: `limit=20`, optional `status=<filter>`, `offset=<n>` for pagination.
- No backend changes required.

## 6. Testing
- `vue-tsc --noEmit` passes with zero errors.

## 7. Risks & Mitigations
- **Empty table**: Shows empty state message when no decisions match filter.
- **Large datasets**: Pagination via "Load more" prevents loading too much data at once.

## 8. Acceptance Criteria Verification
- [x] EntryDecision interface exists with all 10 fields
- [x] Filter tabs switch displayed decisions
- [x] Table shows time, symbol, status badge, stage, reason codes, regime, profile
- [x] Clicking row expands to show reason_text
- [x] Status badges use correct color coding
- [x] vue-tsc passes

## 9. Out of Scope
Backend changes, database migrations, new API endpoints.

## 10. Security
No secrets accessed, no broker APIs called, paper-trading only.

## 11. Performance
Pagination limits initial fetch to 20 items. Filter changes trigger a fresh fetch.

## 12. Next Steps
Approve and merge.

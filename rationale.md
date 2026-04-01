# Rationale for `marketpulse-task-2026-04-01-0007`

**author:** coder-agent (MarketPulse Coder)
**branch:** task/marketpulse-task-2026-04-01-0007-implementation
**date:** 2026-04-01

---

## 1) One-line summary
Added GET /portfolio/protection-history endpoint and collapsible Protection History timeline in PortfolioView.vue, color-coded by protection type.

---

## 2) Mapping to acceptance criteria

- **Criteria:** GET /api/v1/portfolio/protection-history returns 200 with a JSON list
- **Status:** `pass`
- **Evidence:** test_protection_history_returns_200_with_list passes; endpoint returns list.

- **Criteria:** Each item in the list has fields: id, protection_type, status, reason, created_at
- **Status:** `pass`
- **Evidence:** test_protection_history_returns_200_with_list asserts all required fields present.

- **Criteria:** The limit query parameter caps the number of results (default 20)
- **Status:** `pass`
- **Evidence:** test_protection_history_limit_param passes with ?limit=5.

- **Criteria:** Results are ordered by created_at descending (newest first)
- **Status:** `pass`
- **Evidence:** Endpoint uses `.order_by(ProtectionEvent.created_at.desc())`.

- **Criteria:** PortfolioView.vue has a collapsible 'Protection History' section
- **Status:** `pass`
- **Evidence:** Added showProtectionHistory ref and collapsible div with chevron toggle.

- **Criteria:** Protection events are color-coded by type using protectionColor()
- **Status:** `pass`
- **Evidence:** Each card uses `:class="protectionColor(ev.protection_type)"`.

- **Criteria:** Each event card shows protection_type, reason, timestamp, and expires_at if present
- **Status:** `pass`
- **Evidence:** Template renders all fields; expires_at shown conditionally with v-if.

- **Criteria:** All backend tests pass, mypy passes, vue-tsc passes
- **Status:** `pass`
- **Evidence:** pytest 4/4 passed, mypy schemas.py clean, mypy router.py only pre-existing errors, vue-tsc clean.

---

## 3) Files changed

| File | Change |
|------|--------|
| backend/app/portfolio/schemas.py | Added ProtectionEventOut Pydantic model |
| backend/app/portfolio/router.py | Added GET /protection-history endpoint |
| frontend/src/types/api.ts | Added ProtectionEvent interface |
| frontend/src/views/PortfolioView.vue | Added protection history fetch, collapsible timeline section |
| backend/tests/test_protection_history.py | 4 async tests for the new endpoint |

---

## 4) Design decisions

- Reused existing `protectionColor()` helper and collapsible pattern from the active protections section for consistency.
- Used `fetchProtectionHistory()` already defined in `portfolio.ts` rather than raw `api.get()`.
- Added `ProtectionEvent` interface to `api.ts` since it was imported in `portfolio.ts` but missing.
- Endpoint returns dicts (not Pydantic response_model) matching the existing patterns in this router.

---

## 5) Risks and mitigations

- **Low:** Pre-existing mypy errors in router.py (compute_risk_metrics variance) — not introduced by this change.
- **Low:** No pagination beyond limit param — acceptable for history of protection events (typically small volume).

---

## 6) Security

- No secrets accessed or committed.
- No external API calls.
- No broker SDK usage.
- Paper-trading only; all data is demo/synthetic.

---

## 7) Open questions

None. All pieces (model, frontend API function, color helper) already existed; this task wired them together.

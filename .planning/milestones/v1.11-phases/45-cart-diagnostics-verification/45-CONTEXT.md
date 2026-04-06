# Phase 45: Cart Diagnostics & Verification - Context

**Gathered:** 2026-04-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Expose the new cart add flow clearly enough to debug and verify it end to end. This phase covers backend/admin diagnostics for add latency and reconciliation outcomes, plus repeatable automated and lightweight browser/manual verification for the new pending-aware cart flow. It does not redesign the cart UI again and does not change the core add/set-quantity semantics from Phases 43-44 unless a verification gap forces a minimal fix.

</domain>

<decisions>
## Implementation Decisions

### Diagnostics Surface
- **D-01:** New diagnostics should surface through **admin/status and backend logs**, not through new user-facing MiniApp UI.
- **D-02:** Diagnostics should stay targeted to the cart flow rather than becoming a general observability platform in this phase.

### Timing And Outcome Data
- **D-03:** Record timing and outcome across the full cart attempt lifecycle:
  - add request started
  - add returned `success` / `pending` / `failed`
  - status lookup / reconciliation result
  - final outcome
  - total duration until final truth
- **D-04:** Keep timeout class and reconciliation source visible enough to distinguish:
  - immediate success
  - pending then success
  - pending then failure
  - clear upstream/backend failure

### Verification Strength
- **D-05:** Verification should include strong automated backend coverage for:
  - immediate success
  - pending → success
  - pending → failure
  - quantity/set-quantity flow
- **D-06:** Add one lightweight browser/manual sanity path for the visible 5-second UX contract, rather than a large new Playwright suite.

### the agent's Discretion
- Exact metric field names and payload shape for cart diagnostics, as long as duration, timeout class, reconciliation source, and final outcome remain inspectable.
- Exact admin/log presentation format, as long as operators can see recent cart attempt behavior without digging into raw code.
- Exact verification helper structure, as long as the final artifacts are repeatable and Phase 45 can prove the bounded cart contract did not regress.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope & Requirements
- `.planning/ROADMAP.md` — Phase 45 goal, requirements mapping, and success criteria.
- `.planning/REQUIREMENTS.md` — `OPS-04` and `QA-04` define the diagnostics and regression obligations.
- `.planning/PROJECT.md` — Current milestone framing and accumulated cart decisions.
- `.planning/STATE.md` — Current routing and phase position.

### Prior Cart Contract Work
- `.planning/phases/43-backend-cart-response-contract/43-CONTEXT.md` — Backend pending contract, dedupe semantics, and add-status lifecycle.
- `.planning/phases/44-frontend-bounded-add-ux/44-CONTEXT.md` — Frontend pending behavior, synced quantity controls, and confirmed-only failure treatment.
- `backend/main.py` — Current `/api/cart/add`, `/api/cart/add-status/{attempt_id}`, `/api/cart/items`, `/api/cart/set-quantity`, and `/admin/status` implementation.
- `cart/vkusvill_api.py` — Current bounded add behavior and cart quantity helpers.

### Existing Diagnostics Surfaces
- `backend/admin.html` — Current admin dashboard refresh cycle, status cards, log filters, and cookie warnings.
- `backend/main.py:/admin/status` — Current admin payload contract.
- `backend/test_admin_routes.py` — Existing admin/status route tests that can be extended for cart diagnostics.

### Existing Verification Assets
- `backend/test_cart_items_fallback.py` — Legacy timeout and bounded cart-client tests.
- `backend/test_cart_pending_contract.py` — Current pending/add-status and quantity route tests from Phases 43-44.
- `miniapp/test_ui.py` — Existing lightweight browser/manual verification script that can be adapted instead of creating a large new E2E suite.
- `.planning/codebase/TESTING.md` — Current backend/frontend test landscape and gaps.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/main.py` already has an in-memory pending attempt registry with timestamps, status, source, and `last_error` fields.
- `/admin/status` and `backend/admin.html` already provide a place to surface recent operational state without adding a new operator UI surface.
- `backend/test_cart_pending_contract.py` already covers the basic pending/success/failure and quantity route contract, so Phase 45 can extend focused tests rather than starting from scratch.

### Established Patterns
- Backend diagnostics currently rely on standard logger output plus explicit JSON payloads like `sourceFreshness` and `cycleState`.
- Admin UI is a polling dashboard that consumes `/admin/status` and log endpoints, not a separate SPA.
- The repo already accepts lightweight targeted browser checks in `miniapp/test_ui.py` instead of requiring a full formal E2E framework.

### Integration Points
- `backend/main.py` is the primary place to add cart lifecycle timing fields and expose them to admin/status.
- `backend/admin.html` is the natural place to display recent cart attempt diagnostics if route payloads are extended.
- `backend/test_cart_pending_contract.py`, `backend/test_cart_items_fallback.py`, and `backend/test_admin_routes.py` are the test surfaces for the automated verification part.
- `miniapp/test_ui.py` is the likely place for the lightweight visible-flow sanity check.

</code_context>

<specifics>
## Specific Ideas

- The user wants the new cart flow to be inspectable, not mysterious, after the big behavior changes in Phases 43-44.
- The new quantity/set-quantity path should be covered explicitly, not treated as incidental.
- Diagnostics should help explain whether slow add issues came from initial add timeout, later status lookup, or a final confirmed failure.

</specifics>

<deferred>
## Deferred Ideas

- General-purpose observability dashboards or historical percentile trends beyond what is needed to inspect recent cart behavior are out of scope for this phase.
- The stale-banner wording todo remains separate from Phase 45’s cart diagnostics scope.

### Reviewed Todos (not folded)
- `2026-04-06-clarify-stale-banner-freshness-vs-updated-time.md` — valid admin/UI clarity issue, but not part of the cart diagnostics and regression contract.

</deferred>

---

*Phase: 45-cart-diagnostics-verification*
*Context gathered: 2026-04-06*

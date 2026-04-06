# Phase 43: Backend Cart Response Contract - Context

**Gathered:** 2026-04-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Bound backend cart-add latency and stop the current inline timeout-recovery chain from stretching one add request. This phase defines what `/api/cart/add` returns when VkusVill is slow or ambiguous, preserves enough attempt identity for later reconciliation, and keeps clear failures distinct from unknown outcomes. It does not redesign the card/cart controls; that frontend behavior belongs to Phase 44.

</domain>

<decisions>
## Implementation Decisions

### Response Budget & Outcome Contract
- **D-01:** Treat the backend hot-path budget as approximately **1.5 seconds** for deciding the add result. This is a "stop waiting and return pending" budget, not a hard success/failure SLA for VkusVill itself.
- **D-02:** If add truth is still unknown when that budget is exhausted, return a distinct **pending / unknown** outcome instead of blocking longer or converting it to an error.
- **D-03:** Remove the current inline timeout recovery that does an immediate cart read inside the same add request after timeout. Late cart truth should be reconciled after the response path, not inside it.

### Failure Classification
- **D-04:** Return a real failure only for clear cases such as unauthenticated user, explicit sold-out / invalid-product responses, or clear upstream unavailable / malformed-response conditions.
- **D-05:** Slow or ambiguous upstream behavior should map to **pending**, not **error**.

### Attempt Identity & Duplicate Protection
- **D-06:** While one add attempt is unresolved, treat the same **user + product** as one pending attempt for a short dedupe window (target: roughly **3-5 seconds**) so the backend does not send duplicate upstream add requests.
- **D-07:** Backend dedupe is a safety net for race conditions. The main user-facing behavior should still be that once a product is effectively in-cart, all UI surfaces switch away from a plain add button instead of registering another add.

### the agent's Discretion
- Exact response payload shape and naming for the new pending state, as long as frontend can reliably distinguish `success`, `pending`, and real failure.
- Exact storage/mechanism for short-lived pending-attempt tracking, as long as it is scoped by user + product and survives the normal request race window.
- Exact reconciliation trigger and logging details, as long as late-success vs hard-failure outcomes remain inspectable.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope & Milestone Contract
- `.planning/ROADMAP.md` — Phase 43 goal, requirement mapping, and success criteria.
- `.planning/REQUIREMENTS.md` — `CART-06` and `CART-09` define the backend cart-truth and bounded-response requirements.
- `.planning/PROJECT.md` — Active milestone framing for cart responsiveness and truth recovery.
- `.planning/STATE.md` — Current milestone notes and the known bug describing the current overlong cart flow.

### Current Cart Add Implementation
- `backend/main.py` — `/api/cart/add` endpoint currently turns timeout into `504` and only distinguishes a small set of upstream errors.
- `cart/vkusvill_api.py` — Current cart client session warmup, add request, timeout handling, and inline timeout recovery via `get_cart()`.
- `docs/memory/KNOWLEDGE_BASE.md` — Existing reverse-engineered VkusVill cart payload notes referenced by the cart client.

### Frontend Consumers Of The Contract
- `miniapp/src/App.jsx` — Current `handleAddToCart` timeout budget, abort path, and inline `refreshCartState(3, 1200)` reconciliation that this phase is meant to unblock.
- `miniapp/src/ProductDetail.jsx` — Secondary add-to-cart entry point that shares the same backend contract and can race with the main product card.

### Prior Decisions & Architecture Context
- `.planning/phases/21-backend-proxy-unification/21-CONTEXT.md` — Existing decision that VkusVill backend traffic should keep using ProxyManager-managed paths.
- `.planning/phases/41-main-screen-card-performance/41-CONTEXT.md` — Prior decision to preserve current cart/detail behavior unless a measured improvement requires change.
- `.planning/codebase/ARCHITECTURE.md` — Current backend/frontend/cart integration shape and where the add flow fits in the system.
- `.planning/codebase/INTEGRATIONS.md` — VkusVill cart AJAX endpoints and deployment integration context.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `cart/vkusvill_api.py:VkusVillCart` already encapsulates session loading, proxy-aware VkusVill requests, add, and cart reads.
- `backend/main.py:/api/cart/add` is already the single backend entry point for web add-to-cart behavior.
- `miniapp/src/App.jsx:refreshCartState()` already exists for later reconciliation and can be moved off the main click path instead of deleted entirely.

### Established Patterns
- The backend currently maps VkusVill timeouts to `504`, which makes the frontend treat an ambiguous result like a hard failure unless it does extra inline checks.
- The cart client can do multiple network steps in one add path: cookie/session load, optional warmup GET, add POST, then cart read on timeout.
- The frontend currently has two add entry points for the same product contract: main card and detail drawer.
- VkusVill-facing backend traffic is expected to keep using ProxyManager rather than switching to a direct-only path.

### Integration Points
- `backend/main.py:/api/cart/add` is the main place to change the response contract from timeout-as-error to pending-aware behavior.
- `cart/vkusvill_api.py:add()` is where inline timeout recovery should be removed or restructured into a bounded pending outcome.
- `miniapp/src/App.jsx` and `miniapp/src/ProductDetail.jsx` will need to consume the new backend pending state in Phase 44.

</code_context>

<specifics>
## Specific Ideas

- The user expects add-to-cart to stay fast because it usually responds quickly; the extra visible wait should not come from chained fallback logic.
- The user accepted **~1.5 seconds** as the backend "stop waiting and return pending" budget instead of a brittle 1.0-second cutoff.
- The current reverse-engineered AJAX cart API should stay in place; the goal is to make it more robust, not replace it with browser clicks.
- Long-term frontend behavior should switch successful products into an in-cart quantity control across all visible copies of that product instead of leaving a plain add button in place.

</specifics>

<deferred>
## Deferred Ideas

- Persistent in-card quantity controls, cross-surface control syncing, and direct numeric quantity entry for both weighted (`0.73 кг`) and counted (`2 шт`) items belong to **Phase 44**, not this backend contract phase.

### Reviewed Todos (not folded)
- `2026-04-02-history-search-shows-all-matching-products-from-catalog.md` — surfaced only on generic backend keywords and does not affect the cart response contract; keep deferred.

</deferred>

---

*Phase: 43-backend-cart-response-contract*
*Context gathered: 2026-04-06*

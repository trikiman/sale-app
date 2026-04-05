# Phase 41: Main Screen & Card Performance - Context

**Gathered:** 2026-04-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Remove the slow initial loading feel and laggy card interactions on the main MiniApp screen. This phase covers faster first useful content, reducing card enrichment lag, and measuring any card/detail data-path changes before adopting them. It does not redesign the card UI, rework unrelated pages, or commit to a reverse-engineered/private API unless measurements prove it is clearly better.

</domain>

<decisions>
## Implementation Decisions

### Scope Of Optimization
- **D-01:** Keep the current main card UI and overall layout mostly the same. This phase is a performance pass, not a visual redesign.
- **D-02:** Prioritize the **initial main-screen load** and **laggy card behavior** first.
- **D-03:** Existing favorites, cart, and detail interactions must keep their current user-facing behavior.

### Data Path Changes
- **D-04:** Only change the card/detail data path if the change is supported by measured latency or responsiveness improvement.
- **D-05:** A reverse-engineered/private API path is allowed only if it proves **clearly faster and more reliable** than the current path.
- **D-06:** If the existing path can be optimized enough without a new private API dependency, prefer that simpler route.

### the agent's Discretion
- Exact rendering and data-fetching optimizations, as long as they improve the main-screen/card feel without changing the UI contract.
- Exact measurement approach for comparing the current path vs any alternate API/data path.
- Exact loading-state treatment, as long as it reduces the long blocking feel and does not create misleading stale UI.

</decisions>

<specifics>
## Specific Ideas

- The main pain is the first open of the main sale screen, where the loading state feels too long.
- Product cards also feel laggy, likely because visible cards trigger extra detail/weight fetches after the main product payload arrives.
- The user explicitly wants optimization first, and only wants a reverse-engineered/private API if it is clearly justified by results.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope
- `.planning/ROADMAP.md` — Phase 41 goal, requirements mapping, and success criteria
- `.planning/REQUIREMENTS.md` — UI-16, UI-17, and UI-18 define the load/performance contract
- `.planning/PROJECT.md` — milestone framing for main-screen/card lag
- `.planning/STATE.md` — current milestone notes and known main-screen performance issue

### Existing Performance & UI Logic
- `miniapp/src/App.jsx` — main load path, SSE/polling refresh, visible-card weight enrichment, loading state, and stale banners
- `miniapp/src/ProductDetail.jsx` — detail fetch path and timeout behavior
- `miniapp/src/productMeta.js` — current weight merge and "needs extra fetch" logic
- `backend/main.py` — `/api/products` payload shape and `/api/product/{product_id}/details` path
- `miniapp/test_ui.py` — existing browser smoke checks

### Prior Decisions & Codebase Guides
- `.planning/phases/19-rendering-load-speed/19-CONTEXT.md` — prior performance-phase decisions and the repo’s existing "optimize behavior without redesign" precedent
- `.planning/codebase/ARCHITECTURE.md` — current frontend/backend data flow
- `.planning/codebase/TESTING.md` — current frontend/backend testing infrastructure and gaps

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `miniapp/src/App.jsx` already memoizes `ProductCard` and uses infinite scroll, so Phase 41 can build on that instead of replacing the feed.
- `miniapp/src/productMeta.js` already isolates weight merge and missing-weight detection logic.
- `backend/main.py:/api/product/{id}/details` already falls back gracefully when detail scraping fails, so the performance work can optimize around an existing contract.

### Established Patterns
- Main-screen data is still loaded with one blocking `/api/products` fetch before the grid appears.
- Missing weights are fetched lazily per visible card via `/api/product/{id}/details`, which can create follow-up lag even after the main list arrives.
- The app already uses banners/toasts for feedback and does not rely on modal alerts.

### Integration Points
- `miniapp/src/App.jsx` is the primary place to reduce blocking first-load behavior and card-level follow-up work.
- `miniapp/src/productMeta.js` and `backend/main.py` are the natural places to reduce unnecessary weight/detail fetches.
- `miniapp/src/ProductDetail.jsx` may need tuning if detail fetches are causing visible lag or contention.

</code_context>

<deferred>
## Deferred Ideas

- Full card redesign or brand refresh — out of scope for this performance phase
- Mandatory migration to a reverse-engineered/private API without first proving a clear win

</deferred>

---

*Phase: 41-main-screen-card-performance*
*Context gathered: 2026-04-05*

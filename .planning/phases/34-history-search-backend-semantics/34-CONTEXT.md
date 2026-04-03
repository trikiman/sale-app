# Phase 34: History Search Backend Semantics - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the History API and search-mode filtering behave like an intentional local-catalog search instead of a history-only list with a text box. This phase covers backend query semantics and the existing search/filter contract between `backend/main.py` and `HistoryPage.jsx`. It does not add remote VkusVill search parity, new ranking systems, or the visual treatment of mixed result states.

</domain>

<decisions>
## Implementation Decisions

### Search Dataset Scope
- **D-01:** When `search` is non-empty, `/api/history/products` must query the full local `product_catalog` and must not apply the default `pc.total_sale_count > 0` gate. Search remains local-only in this phase; do not call VkusVill's remote search.
- **D-02:** Keep the existing search normalization and fuzzy fallback behavior, but make both exact and fallback search run against the same full local catalog scope so live-sale and zero-history products are eligible either way.

### Search Filter Semantics
- **D-03:** Search removes only the implicit history-only restriction. Explicit user-selected filters (`filter`, `group`, `subgroup`) still apply when present, because those are intentional constraints rather than hidden dataset limits.
- **D-04:** While search is active, group/subgroup chips should continue to use the full-catalog scope (`/api/groups?scope=all`) so users can refine catalog-wide search results without falling back to the history-only group list.
- **D-05:** Do not introduce a separate search-only endpoint or a second search DTO. Phase 34 should preserve the existing request contract and tighten semantics inside the current `/api/history/products` and `/api/groups` paths.

### Result Contract
- **D-06:** Keep the existing History API response shape for all search results. Catalog-only products with no sale history should still return normal cards with `total_sale_count = 0`, `is_currently_on_sale = false`, no prediction fields, and any available catalog metadata instead of being modeled as a separate result type.
- **D-07:** Continue deriving live-sale state from `sale_sessions` for the returned product IDs. This phase does not add a new denormalized search table or alternate source of truth for live availability.

### Regression Coverage
- **D-08:** Backend regression tests should exercise three fixture classes explicitly: currently-on-sale matches, history-only matches, and catalog-only matches with zero sale history. Use the existing pytest + FastAPI `TestClient` pattern rather than introducing a new harness.

### the agent's Discretion
- Exact SQL/query-builder refactor shape inside `backend/main.py`
- Whether the regression tests extend `backend/test_api.py` or live in a new targeted backend test file
- Small comment/docstring updates that clarify search-mode behavior for future phases

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope
- `.planning/ROADMAP.md` — Phase 34 goal, requirements mapping, and success criteria
- `.planning/REQUIREMENTS.md` — HIST-05, HIST-06, and HIST-07 define the semantic contract for search completeness
- `.planning/PROJECT.md` — milestone framing and the explicit boundary that remote-search parity is out of scope here
- `.planning/todos/pending/2026-04-02-history-search-shows-all-matching-products-from-catalog.md` — originating bug report and expected "show everything that matches locally" behavior

### Existing Backend Contract
- `backend/main.py` — `/api/history/products` search branch, fuzzy fallback, current-sale enrichment, and prediction enrichment
- `backend/main.py` — `/api/groups` scope handling for `history` vs `all`

### Existing Frontend Integration
- `miniapp/src/HistoryPage.jsx` — search debounce, `groupsScope = search ? 'all' : 'history'`, filter param construction, and existing ghost-card rendering

### Prior Decisions
- `.planning/phases/29-subgroup-data-layer/29-CONTEXT.md` — group/subgroup data model and history API context from the hierarchy work
- `.planning/phases/33-group-subgroup-notifications/33-CONTEXT.md` — recent precedent for using `product_catalog` as a resilient metadata source when runtime views are incomplete

### Codebase Guides
- `.planning/codebase/CONVENTIONS.md` — backend/frontend conventions and error-handling patterns
- `.planning/codebase/TESTING.md` — pytest/TestClient patterns and current coverage gaps

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/main.py:/api/history/products` already normalizes copied search text, supports fuzzy fallback, and enriches returned IDs with `is_currently_on_sale` and `last_old_price`
- `backend/main.py:/api/groups` already supports `scope=all`, so Phase 34 can lean on an existing full-catalog group source instead of inventing a new API
- `miniapp/src/HistoryPage.jsx` already switches `groupsScope` to `all` during search and already renders ghost/no-data cards when `total_sale_count === 0`
- `backend/test_api.py` and sibling backend tests already use pytest with FastAPI `TestClient`, which is the lowest-friction regression pattern for this phase

### Established Patterns
- Backend endpoints prefer returning empty-but-valid payloads instead of raising hard API errors
- History search already relies on `product_catalog` as the primary search dataset and `sale_sessions` for live-sale enrichment
- Client search intentionally clears active sale-type filters when typing so search is not silently narrowed by stale UI state
- Predictions are only enriched for products that have recorded sale history; zero-history catalog products naturally skip that branch

### Integration Points
- The search semantics change belongs in the query-building branch of `backend/main.py:/api/history/products`
- Group/subgroup search visibility is controlled by the interaction between `backend/main.py:/api/groups` and `miniapp/src/HistoryPage.jsx`
- Regression coverage should hit the backend endpoint contract first, because Phase 35 will depend on these backend semantics being stable

</code_context>

<specifics>
## Specific Ideas

- The sanity-check example from the originating todo is a search like `цезарь` where a product is currently on sale now but still needs to appear in History search results.
- Phase 34 should preserve the existing local-catalog architecture and deliberately stop short of "VkusVill search parity" beyond what exists in `product_catalog`.
- Catalog-only products should remain valid search hits even if their richer presentation is deferred to Phase 35.

</specifics>

<deferred>
## Deferred Ideas

- Remote VkusVill search parity beyond the local `product_catalog` snapshot — future requirement `SRCH-04`, not a Phase 34 backend-semantics change
- Visual differentiation, labels, and empty-state polish for live/history/catalog-only result states — Phase 35 owns that work
- Search-specific ranking or relevance tuning beyond the existing sort controls — defer unless Phase 34 proves the current ordering is insufficient

</deferred>

---

*Phase: 34-history-search-backend-semantics*
*Context gathered: 2026-04-04*

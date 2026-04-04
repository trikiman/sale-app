# Phase 36: Supplemental Catalog Discovery - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Add an offline discovery path for VkusVill products that the current hardcoded category crawl does not capture. This phase is about finding stable product IDs and collecting a repeatable discovery snapshot for missing products. It does not yet merge discoveries into `category_db.json` or `product_catalog`, and it does not change History search runtime behavior.

</domain>

<decisions>
## Implementation Decisions

### Discovery Path
- **D-01:** Supplemental discovery stays offline. Do not add runtime hybrid search or per-user remote search calls in this phase.
- **D-02:** Keep the current `scrape_categories.py` category crawl intact and add a separate supplemental discovery step/script for the missing-product path. Phase 36 should discover candidates without rewriting the main category crawler.
- **D-03:** Reuse the existing HTTP scraper style: low-concurrency requests, proxy-compatible transport, and no browser/login/SMS dependency. Prefer `aiohttp`-style direct requests over `nodriver` unless a hard blocker proves that impossible.

### Discovery Inputs
- **D-04:** Drive discovery from a repo-tracked seed query set so refreshes are repeatable. Start from known parity-gap queries and broaden only as needed; do not make the discovery run depend on ad hoc manual searches.
- **D-05:** Fold the pending todo `2026-04-02-history-search-shows-all-matching-products-from-catalog.md` into this phase as an acceptance target for discovery inputs. The canonical example query `цезарь` must be represented in the seed set or verification notes for the phase.

### Discovery Output Contract
- **D-06:** Phase 36 writes a separate sidecar discovery artifact keyed by stable `product_id`, not directly into `category_db.json` or `product_catalog`. Phase 37 will own merge/backfill into the main local catalog artifacts.
- **D-07:** A discovered record is only valid if it includes a stable numeric VkusVill `product_id`. Discard records that cannot be tied to a durable local key.
- **D-08:** Discovery records should keep the best available metadata that can help later merge work: `name`, canonical product URL when available, image hint when available, any category/group/subgroup hint when available, source query/source type, and discovery timestamp. Missing hierarchy is acceptable at this stage if the product identity is stable.

### Pipeline Compatibility
- **D-09:** Existing downstream consumers (`scrape_merge.py`, `database/sale_history.py`, `/api/history/products`) should remain unchanged during this phase and continue reading the current catalog artifacts until Phase 37 merges the new discovery data.
- **D-10:** Phase 36 should produce enough summary stats to show whether discovery is actually finding net-new products for the local catalog, even before those products are merged into the main DB.

### Agent's Discretion
- Exact filename and schema shape for the supplemental discovery artifact
- How seed queries are grouped, normalized, and paginated during a run
- The exact balance between targeted known-gap queries and broader exploratory seed coverage
- The precise HTTP endpoint/response parsing approach, as long as it stays offline and yields stable product IDs

### Folded Todos
- `2026-04-02-history-search-shows-all-matching-products-from-catalog.md` — folded as a parity target for the discovery seed set and later verification. Only the “VkusVill has products our local catalog lacks” part is in scope here; the runtime search semantics bug was already fixed in v1.8.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope
- `.planning/ROADMAP.md` — Phase 36 goal, requirement mapping, and success criteria
- `.planning/REQUIREMENTS.md` — DATA-04 defines the discovery requirement; SRCH-04/SRCH-05/QA-02/OPS-01 define the downstream contract this discovery must enable
- `.planning/PROJECT.md` — milestone framing and the explicit local-first decision for v1.9
- `.planning/STATE.md` — active milestone status and current focus

### Originating Gap Report
- `.planning/todos/pending/2026-04-02-history-search-shows-all-matching-products-from-catalog.md` — records the observed parity gap and the concrete `цезарь` example

### Prior Decisions
- `.planning/phases/29-subgroup-data-layer/29-CONTEXT.md` — existing `category_db.json` / `product_catalog` hierarchy model and prior category-pipeline decisions
- `.planning/phases/33-group-subgroup-notifications/33-CONTEXT.md` — precedent for relying on `product_catalog` fallback when runtime JSON is incomplete
- `.planning/phases/34-history-search-backend-semantics/34-CONTEXT.md` — confirms History search remains local-only and that remote parity was intentionally deferred
- `.planning/phases/35-search-result-ux-regression-coverage/35-CONTEXT.md` — confirms v1.8 solved presentation clarity but not catalog completeness

### Codebase Guides
- `.planning/codebase/CONVENTIONS.md` — scraper/backend conventions, logging style, and JSON artifact patterns
- `.planning/codebase/INTEGRATIONS.md` — VkusVill integration constraints, proxy setup, and JSON data flow
- `.planning/codebase/TESTING.md` — existing lightweight pytest/unit test patterns and coverage gaps

### Existing Pipeline Files
- `scrape_categories.py` — current hardcoded category crawler, product ID extraction, JSON save pattern, and proxy-aware aiohttp flow
- `scrape_merge.py` — current enrichment path from `category_db.json` into merged sale products
- `database/sale_history.py` — `seed_product_catalog()` and `record_sale_appearances()` define how local catalog data reaches `product_catalog`
- `backend/main.py` — `/api/history/products` and `/api/groups` read the local `product_catalog` that this milestone is trying to strengthen

### Existing Tests
- `backend/test_categories.py` — current unit-style coverage for category scraper parsing and `category_db.json` persistence helpers
- `backend/test_history_search.py` — current targeted regression coverage for local-catalog History search behavior

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scrape_categories.py` already provides proxy-aware `aiohttp` fetching, stable VkusVill product ID extraction, and JSON artifact save/load helpers that Phase 36 can reuse or mirror
- `scrape_merge.py` already enriches runtime product JSON from `category_db.json`, so a sidecar discovery artifact can stay isolated until Phase 37 intentionally merges it
- `database/sale_history.py:seed_product_catalog()` already seeds and updates `product_catalog` from `category_db.json`, which is why Phase 36 should stop short of direct DB mutation
- `backend/test_categories.py` already demonstrates low-friction tests for scraper parsing and temp JSON DB files

### Established Patterns
- Scraper-side integrations prefer JSON artifacts and resilient print-based logging over tightly coupled DB writes
- Product identity across the system is anchored on VkusVill `product_id`, not name matching
- Existing catalog pipeline preserves richer metadata in `category_db.json` and collapses to a single subgroup in `product_catalog`
- Backend runtime paths prefer empty-but-valid responses and should not depend on a brittle discovery source during user requests

### Integration Points
- Phase 36’s discovery output should plug in ahead of `scrape_merge.py` / `seed_product_catalog()` rather than bypassing them
- The most natural compatibility seam is a new supplemental artifact under `data/` that Phase 37 can read and merge into `category_db.json`
- Verification can reuse backend/unit test patterns plus artifact-level assertions before any runtime UI checks

</code_context>

<specifics>
## Specific Ideas

- The current hardcoded category list in `scrape_categories.py` is the visible completeness bottleneck for products that VkusVill live search knows about but category crawl misses.
- The first known-gap example remains a `цезарь` search where VkusVill live search exposes products not present in the local catalog.
- This phase should intentionally create a bridge between “live search knows it” and “local catalog can import it later” without changing the current History API contract.

</specifics>

<deferred>
## Deferred Ideas

- Runtime hybrid search fallback during user queries — future requirement `SRCH-06`, not a Phase 36 discovery concern
- Merging discoveries into `category_db.json` / `product_catalog` — Phase 37
- Full parity verification against History search results and coverage metrics dashboards — Phase 38
- Multi-subgroup DB fidelity beyond the existing single-subgroup `product_catalog` field — future requirement `DATA-08`

</deferred>

---

*Phase: 36-supplemental-catalog-discovery*
*Context gathered: 2026-04-04*

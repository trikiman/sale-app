# Phase 36: Supplemental Catalog Discovery - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Build an offline catalog-discovery layer that scrapes every catalog tile/source from VkusVill, tracks completion per source using that source's live count, and stores discovery data outside the main local catalog. This phase is about source-by-source collection, source progress tracking, and failure handling. It does not merge into `category_db.json` or `product_catalog`, and it does not change runtime History search behavior.

</domain>

<decisions>
## Implementation Decisions

### Source Model
- **D-01:** Treat every catalog tile/source on the VkusVill catalog page as a discovery source. Do not try to separate "base" vs "overlay" categories in this phase.
- **D-02:** Overlapping sources are acceptable. A product may appear in multiple sources; that is not an error during collection.
- **D-03:** Do not use source counts to build one summed global total. Source counts are only used as completion targets for that specific source.

### Completion Logic
- **D-04:** Each source has its own live expected count, taken from that source page on VkusVill.
- **D-05:** A source is complete only when the current scrape confirms `collected == expected` for that source.
- **D-06:** If a source says `1418` and the scrape only has `1409`, that source is incomplete. Partial is not valid.
- **D-07:** A source file existing is not proof of validity. Only a fresh successful run against the current live count can mark the source complete.

### Storage Model
- **D-08:** Store discovery output separately from the main catalog. Do not write directly into `category_db.json` or `product_catalog` in Phase 36.
- **D-09:** Use separate temp files per source/category for robustness rather than one monolithic discovery file during collection.
- **D-10:** After source collection, later phases can merge all source files and dedupe them into a unified discovery catalog.

### Failure Handling
- **D-11:** Incomplete runs keep already scraped items and try to fill the gap on later runs.
- **D-12:** Failures and mismatches must be visible in the admin panel logs.
- **D-13:** A failed/incomplete source is not valid even if it has many items already collected.
- **D-14:** Stale-item risk between failed runs is acceptable for now, because only a fresh run that matches the current live count can mark the source complete.

### Identity & Deduplication
- **D-15:** Duplicates are expected across sources and are handled later during merge.
- **D-16:** The identity key must be verified during research/execution. `product_id` is the preferred candidate, but Phase 36 should validate that it is stable enough before hard-locking dedupe on it.

### Pipeline Boundary
- **D-17:** Runtime search remains local-first in this phase. No hybrid runtime search.
- **D-18:** Phase 36 ends with source-level discovery artifacts and source-level completeness state, not with main-catalog merge.

### Agent's Discretion
- Exact naming for source files and source-state metadata
- Exact admin-log structure for mismatch/failure reporting
- Exact scrape strategy per source page, as long as source-level count validation is preserved
- Exact identity-validation method for the preferred `product_id` key

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope
- `.planning/ROADMAP.md` — Phase 36 goal and success criteria
- `.planning/REQUIREMENTS.md` — DATA-04 plus downstream Phase 37/38 requirements this phase must enable
- `.planning/PROJECT.md` — milestone framing and local-first search boundary
- `.planning/STATE.md` — current milestone and phase status

### Prior Decisions
- `.planning/phases/29-subgroup-data-layer/29-CONTEXT.md` — current category/hierarchy pipeline
- `.planning/phases/34-history-search-backend-semantics/34-CONTEXT.md` — remote runtime search remains out of scope
- `.planning/phases/35-search-result-ux-regression-coverage/35-CONTEXT.md` — v1.8 solved local search UX, not catalog completeness

### Existing Pipeline Files
- `scrape_categories.py` — current category crawler, paging pattern, product extraction helpers
- `scrape_merge.py` — current runtime enrichment from local catalog artifacts
- `database/sale_history.py` — current path into `product_catalog`
- `backend/main.py` — current admin-run patterns and runtime readers of the local catalog

### Existing Tests
- `backend/test_categories.py` — current scraper/unit test style
- `backend/test_history_search.py` — current local History search regression coverage

### Originating Gap Context
- `.planning/todos/pending/2026-04-02-history-search-shows-all-matching-products-from-catalog.md` — original missing-catalog signal

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scrape_categories.py` already has low-concurrency HTTP fetching, page parsing, paging, and JSON save patterns
- `backend/main.py` already has background-run/admin-log patterns that Phase 36 can reuse for source runs and failure reporting
- `backend/test_categories.py` already provides the right style for parser- and artifact-level tests

### Established Patterns
- Scraper-side work uses JSON artifacts and print/log-based operational visibility
- Runtime paths depend on the main local catalog and should stay isolated from discovery-only artifacts in this phase
- The current repo already tolerates partial operational states as long as the system does not falsely mark them complete

### Integration Points
- Phase 36 should sit before `scrape_merge.py` and `seed_product_catalog()`, not bypass them
- Source-level files and source-status metadata are the natural Phase 36 outputs
- Admin panel logging should be the operational surface for mismatch/failure visibility

</code_context>

<specifics>
## Specific Ideas

- The important count is per source page, not one global sum across categories.
- The same product can legitimately appear in multiple sources such as `Готовая еда` and `Постное и вегетарианское`.
- Separate source files are preferred because a broken run in one source should not put all discovery progress at risk.

</specifics>

<deferred>
## Deferred Ideas

- Merging source files into a unified deduped discovery catalog — Phase 37
- Writing discovery results into `category_db.json` or `product_catalog` — Phase 37
- Full parity verification against runtime History search — Phase 38
- Runtime hybrid search fallback — future work after local catalog expansion

</deferred>

---

*Phase: 36-supplemental-catalog-discovery*
*Context gathered: 2026-04-04*

# Phase 37: Catalog Merge & Backfill - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Merge Phase 36 discovery source files into stable local catalog artifacts and backfill `product_catalog` without clobbering richer existing metadata. This phase covers deduped discovery merge, `category_db.json` updates, and `product_catalog` backfill. It does not change History search semantics or final parity verification flows.

</domain>

<decisions>
## Implementation Decisions

### Merge Inputs
- **D-01:** Phase 37 consumes the per-source discovery files from `data/catalog_discovery_sources/` and the source-state contract from `data/catalog_discovery_state.json`.
- **D-02:** Stable-source completion from Phase 36 is the merge gate. Personalized/non-blocking source `set-vashi-skidki` must not block the merge.

### Dedupe Model
- **D-03:** Merge discovery files by the validated identity key from Phase 36, which is currently numeric `product_id`.
- **D-04:** Cross-source duplicates are expected and must be merged into one canonical discovered product record with source membership retained.

### Local Catalog Update Rules
- **D-05:** Existing `category_db.json` rows keep their richer category/group/subgroup fields. Discovery data must not overwrite non-empty richer metadata with weaker source-derived hints.
- **D-06:** New products discovered in Phase 36 must be added to `category_db.json` even when taxonomy is still incomplete. Minimal valid discovery metadata is enough: `name`, `image_url` when available, and source membership/provenance.
- **D-07:** `product_catalog` backfill should add newly discovered products so they are searchable locally after refresh, even if `category`, `group_name`, or `subgroup` remain blank.
- **D-08:** Discovery merge may fill blanks such as missing `image_url`, but must not degrade existing non-empty local metadata.

### Pipeline Shape
- **D-09:** Keep discovery merge as an explicit script/step rather than silently wiring Phase 36 temp files straight into runtime readers.
- **D-10:** Phase 37 should produce a deduped merged discovery artifact before or alongside updating `category_db.json`, so the merge output is inspectable and testable.

### Agent's Discretion
- Exact merged discovery filename and schema
- Exact source-membership field names in merged discovery / `category_db.json`
- Whether `product_catalog` backfill happens inside one merge script or by extending `seed_product_catalog()`

</decisions>

<canonical_refs>
## Canonical References

### Phase Scope
- `.planning/ROADMAP.md`
- `.planning/REQUIREMENTS.md`
- `.planning/STATE.md`
- `.planning/PROJECT.md`

### Phase 36 Outputs
- `.planning/phases/36-supplemental-catalog-discovery/36-CONTEXT.md`
- `.planning/phases/36-supplemental-catalog-discovery/36-RESEARCH.md`
- `.planning/phases/36-supplemental-catalog-discovery/36-VERIFICATION.md`
- `data/catalog_sources.json`
- `data/catalog_discovery_state.json`
- `data/catalog_discovery_sources/*.json`

### Existing Pipeline Files
- `scrape_merge.py`
- `database/sale_history.py`
- `utils.py`
- `backend/main.py`

### Existing Tests
- `backend/test_catalog_discovery.py`
- `backend/test_history_search.py`
- `backend/test_categories.py`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `database/sale_history.py:seed_product_catalog()` already seeds `product_catalog` from `category_db.json`
- `utils.load_category_db()` already tolerates extra fields in `category_db.json`
- `backend/main.py:/api/history/products` already searches the full local catalog when search is active

### Established Patterns
- Local catalog data flows through JSON artifacts first, then into SQLite
- Existing consumers rely on `product_catalog` for local search, not directly on temp discovery files

### Integration Points
- `category_db.json` is the bridge between discovery data and `product_catalog`
- `seed_product_catalog()` is the cleanest current backfill seam for adding new rows to `product_catalog`

</code_context>

<specifics>
## Specific Ideas

- Phase 36 proved that source-level collection works and produced enough product identity data to backfill local search even before taxonomy is fully trustworthy.
- The safest Phase 37 merge is additive and metadata-preserving: add new rows, fill blanks, never downgrade richer existing rows.

</specifics>

<deferred>
## Deferred Ideas

- Final parity verification and gap reporting — Phase 38
- Runtime hybrid search fallback
- Deep taxonomy reconciliation across overlapping discovery sources

</deferred>

---

*Phase: 37-catalog-merge-backfill*
*Context gathered: 2026-04-04*

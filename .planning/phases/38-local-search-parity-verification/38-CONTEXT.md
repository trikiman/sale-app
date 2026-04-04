# Phase 38: Local Search Parity Verification - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Verify that the expanded local catalog is actually surfacing newly discovered products in local History search and produce a repeatable parity/gap report. This phase covers parity query selection, live-vs-local verification, and regression coverage around newly backfilled rows. It does not introduce runtime hybrid search.

</domain>

<decisions>
## Implementation Decisions

- **D-01:** Verification should use a repeatable curated query set, not ad hoc screenshots.
- **D-02:** Exact queries for known newly backfilled products are the strongest parity proof for this phase.
- **D-03:** Broad queries such as `цезарь` are still useful as gap signals, but they are not the only acceptance gate.
- **D-04:** Phase 38 should produce an inspectable parity report artifact and keep the search-runtime contract unchanged.
- **D-05:** Phase 36 personalized source `set-vashi-skidki` remains a non-blocking exception and should not block milestone completion.

</decisions>

<canonical_refs>
## Canonical References

- `.planning/ROADMAP.md`
- `.planning/REQUIREMENTS.md`
- `.planning/STATE.md`
- `.planning/phases/36-supplemental-catalog-discovery/36-VERIFICATION.md`
- `.planning/phases/37-catalog-merge-backfill/37-VERIFICATION.md` (to be created in this run)
- `backend/catalog_parity_queries.json`
- `verify_catalog_parity.py`
- `backend/test_history_search.py`
- `backend/test_catalog_parity.py`

</canonical_refs>

<code_context>
## Existing Code Insights

- `verify_catalog_parity.py` can compare live VkusVill search results against the local History API
- `backend/test_history_search.py` already protects the mixed-result local search contract
- `backend/test_catalog_parity.py` now proves blank-taxonomy discovery rows are searchable locally

</code_context>

---

*Phase: 38-local-search-parity-verification*
*Context gathered: 2026-04-04*

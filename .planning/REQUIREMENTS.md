# Requirements: v1.8 History Search Completeness

**Status:** Active milestone
**Created:** 2026-04-03
**Goal:** Make History search return the full local catalog for a query, not just history-backed products.

## History Search Semantics

- [x] **HIST-05**: User can search the History page and see matching products that are currently on sale right now.
- [x] **HIST-06**: User can search the History page and see matching products from `product_catalog` even when they have no recorded sale history yet.
- [x] **HIST-07**: While a search query is active, History page results are not silently restricted by the default history-only dataset or history-scoped group/subgroup state.

## Search Result Clarity

- [ ] **UI-14**: User can tell from each search result whether the product is live on sale now, has past sale history only, or has no sale history yet.
- [ ] **UI-15**: Catalog-only matches with no sale history render as valid search results with clear "no data yet" styling instead of looking broken or missing.

## Verification

- [ ] **QA-01**: Automated coverage protects mixed search results across live-sale, history-only, and catalog-only products.

## Future Requirements

- [ ] **SRCH-04**: Search can surface products beyond the locally scraped `product_catalog` when VkusVill's remote search has extra matches.
- [ ] **DATA-04**: Catalog ingest expands to cover products that the current category scraper does not yet capture.

## Out of Scope

- Querying VkusVill's live remote search endpoint for every History-page search — defer until local catalog completeness is no longer enough.
- Reworking the broader sale-history prediction UX — not needed to fix search completeness.
- Multi-subgroup catalog model redesign — already identified as a separate milestone candidate.

## Traceability

| Requirement | Phase | Final Status | Notes |
|-------------|-------|--------------|-------|
| HIST-05 | 34 | Planned | Search must not lose live on-sale matches |
| HIST-06 | 34 | Planned | Search must include catalog-only items with zero sale history |
| HIST-07 | 34 | Planned | Search mode must bypass history-only scoping rules |
| UI-14 | 35 | Planned | Mixed result states need clear visual cues |
| UI-15 | 35 | Planned | Catalog-only cards should look intentional, not broken |
| QA-01 | 35 | Planned | Regression coverage for live/history/catalog search cases |

# Requirements: v1.9 Catalog Coverage Expansion

**Status:** Milestone implementation complete
**Created:** 2026-04-04
**Goal:** Expand the local catalog so History search can surface more VkusVill products without relying on live remote search per query.

## Catalog Discovery

- [ ] **DATA-04**: Catalog ingest expands beyond the current hardcoded category crawl so products present in VkusVill live search but missing from the local catalog can be discovered offline.
- [x] **DATA-05**: Newly discovered products are persisted into local catalog artifacts (`category_db.json` and `product_catalog`) with stable product IDs, names, and enough metadata to appear in History search.

## Catalog Merge Quality

- [x] **DATA-06**: Multi-source catalog refresh deduplicates products and preserves the best available category/group/subgroup/image metadata instead of clobbering richer existing rows.
- [x] **DATA-07**: Existing local products remain intact during supplemental ingest refreshes; category-derived data and sale-history-backed metadata are not lost when new sources are merged.

## Search Outcome

- [x] **SRCH-04**: After a catalog refresh, History search can surface products that previously existed only in VkusVill remote search, while still serving results from the local catalog.
- [x] **SRCH-05**: The team has a repeatable parity-check query set for formerly missing products, so catalog-expansion progress can be verified intentionally instead of ad hoc screenshots.

## Verification & Operations

- [x] **QA-02**: Automated coverage protects supplemental discovery, multi-source merge dedupe, and representative formerly-missing search queries.
- [x] **OPS-01**: Catalog refresh produces coverage stats or gap signals that make it clear whether local catalog completeness actually improved.

## Future Requirements

- [ ] **SRCH-06**: History search can use live VkusVill search as a hybrid fallback when local catalog expansion still misses a query.
- [ ] **DATA-08**: Local catalog preserves multi-subgroup fidelity in the DB instead of collapsing each product to one subgroup value.

## Out of Scope

- Querying VkusVill live search on every user request in this milestone.
- Reworking History search ranking or UI beyond what is needed to show newly ingested local products.
- General scraper/notifier cleanup unrelated to catalog completeness.

## Traceability

| Requirement | Phase | Final Status | Notes |
|-------------|-------|--------------|-------|
| DATA-04 | 36 | Complete | Source-based offline discovery now scrapes catalog tiles into per-source temp files with source-level completion state |
| DATA-05 | 37 | Complete | Merged discovery data now backfills both `category_db.json` and `product_catalog` |
| DATA-06 | 37 | Complete | Merge is additive and preserves richer existing metadata |
| DATA-07 | 37 | Complete | Existing local rows remain intact while discovery rows fill blanks or add new products |
| SRCH-04 | 38 | Complete | Exact newly backfilled products are now searchable locally |
| SRCH-05 | 38 | Complete | `backend/catalog_parity_queries.json` and `data/catalog_parity_report.json` form the repeatable parity query set/report |
| QA-02 | 38 | Complete | Merge, discovery, parity, and history-search suites now pass together |
| OPS-01 | 38 | Complete | Source-state plus parity report make completeness gains and remaining broad-query gaps visible |

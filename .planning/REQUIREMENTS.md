# Requirements: v1.9 Catalog Coverage Expansion

**Status:** Active milestone
**Created:** 2026-04-04
**Goal:** Expand the local catalog so History search can surface more VkusVill products without relying on live remote search per query.

## Catalog Discovery

- [ ] **DATA-04**: Catalog ingest expands beyond the current hardcoded category crawl so products present in VkusVill live search but missing from the local catalog can be discovered offline.
- [ ] **DATA-05**: Newly discovered products are persisted into local catalog artifacts (`category_db.json` and `product_catalog`) with stable product IDs, names, and enough metadata to appear in History search.

## Catalog Merge Quality

- [ ] **DATA-06**: Multi-source catalog refresh deduplicates products and preserves the best available category/group/subgroup/image metadata instead of clobbering richer existing rows.
- [ ] **DATA-07**: Existing local products remain intact during supplemental ingest refreshes; category-derived data and sale-history-backed metadata are not lost when new sources are merged.

## Search Outcome

- [ ] **SRCH-04**: After a catalog refresh, History search can surface products that previously existed only in VkusVill remote search, while still serving results from the local catalog.
- [ ] **SRCH-05**: The team has a repeatable parity-check query set for formerly missing products, so catalog-expansion progress can be verified intentionally instead of ad hoc screenshots.

## Verification & Operations

- [ ] **QA-02**: Automated coverage protects supplemental discovery, multi-source merge dedupe, and representative formerly-missing search queries.
- [ ] **OPS-01**: Catalog refresh produces coverage stats or gap signals that make it clear whether local catalog completeness actually improved.

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
| DATA-05 | 37 | Planned | Newly discovered products are persisted into `category_db.json` and `product_catalog` |
| DATA-06 | 37 | Planned | Multi-source refresh keeps the richest available metadata per product |
| DATA-07 | 37 | Planned | Existing catalog rows survive supplemental refreshes without destructive overwrite |
| SRCH-04 | 38 | Planned | History search shows newly ingested products from the expanded local catalog |
| SRCH-05 | 38 | Planned | A parity-check query set verifies targeted local-catalog gains |
| QA-02 | 38 | Planned | Regression coverage protects discovery, merge, and search visibility |
| OPS-01 | 38 | Planned | Coverage stats make catalog-completeness gains visible after refreshes |

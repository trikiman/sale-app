# Roadmap: VkusVill Sale Monitor

**Created:** 2026-03-30
**Updated:** 2026-04-04
**Status:** v1.9 roadmap ready — phase 36 not started

## Milestones

- ✅ **v1.0 Bug Fix & Stability** — Phases 1-9 (shipped 2026-03-31)
- ✅ **v1.1 Testing & QA** — Phases 10-12 (shipped 2026-03-31)
- ✅ **v1.2 Price History** — Phases 13-18 (shipped 2026-04-01)
- ✅ **v1.3 Performance & Optimization** — Phases 19-20 (shipped 2026-04-01)
- ✅ **v1.4 Proxy Centralization** — Phases 21-23 (shipped 2026-04-01)
- ✅ **v1.5 History Search & Polish** — Phases 24-26 (shipped 2026-04-01)
- ✅ **v1.6 Green Scraper Robustness** — Phases 27-28 (shipped 2026-04-02)
- ✅ **v1.7 Categories & Subgroups** — Phases 29-33 (shipped 2026-04-03)
- ✅ **v1.8 History Search Completeness** — Phases 34-35 (shipped 2026-04-04)
- 🚧 **v1.9 Catalog Coverage Expansion** — Phases 36-38 (planned 2026-04-04)

## Active Milestone: v1.9 Catalog Coverage Expansion

**Goal:** Expand the local `product_catalog` so History search can find more of the products VkusVill live search already knows about, without switching to per-query hybrid search yet.

**3 phases** | **8 requirements mapped** | All covered ✓

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 36 | Supplemental Catalog Discovery | Add an offline discovery path for products the current category crawl misses. | DATA-04 | 4 |
| 37 | Catalog Merge & Backfill | Merge newly discovered products into local catalog artifacts without metadata loss. | DATA-05, DATA-06, DATA-07 | 4 |
| 38 | Local Search Parity Verification | Prove the expanded local catalog closes targeted search gaps and keep coverage observable. | SRCH-04, SRCH-05, QA-02, OPS-01 | 4 |

### Phase 36: Supplemental Catalog Discovery

**Goal:** Add an offline discovery path for VkusVill products that the current hardcoded category crawl does not capture.
**Requirements:** DATA-04
**Depends on:** —
**Plans:** 2/2 plans complete
**Success Criteria**:
1. Supplemental discovery finds stable product IDs for products absent from the current category crawl.
2. Discovery can run within existing scraper constraints: low concurrency, no SMS/login dependency, and no per-user query path.
3. Discovery output can be refreshed repeatably without duplicating products across runs.
4. Representative known-gap queries now appear in the discovery snapshot for downstream merge.

### Phase 37: Catalog Merge & Backfill

**Goal:** Merge newly discovered products into `category_db.json` and `product_catalog` while preserving the richest available metadata.
**Requirements:** DATA-05, DATA-06, DATA-07
**Depends on:** Phase 36
**Plans:** Not planned yet
**Success Criteria**:
1. Newly discovered products persist into both `category_db.json` and `product_catalog`.
2. Merge logic preserves better existing category/group/subgroup/image metadata instead of overwriting it with poorer supplemental data.
3. Current local databases can be backfilled without a destructive rebuild.
4. Downstream consumers that read `product_catalog` can see the expanded local rows after refresh.

### Phase 38: Local Search Parity Verification

**Goal:** Prove that the expanded local catalog closes targeted search gaps and keep catalog-completeness gains observable.
**Requirements:** SRCH-04, SRCH-05, QA-02, OPS-01
**Depends on:** Phase 37
**Plans:** Not planned yet
**Success Criteria**:
1. History search returns representative formerly missing products from the expanded local catalog after refresh.
2. A parity-check query set exists for repeatable verification instead of ad hoc screenshots.
3. Automated coverage protects discovery, merge, and search visibility for multi-source catalog data.
4. Coverage stats or gap signals make it obvious whether catalog completeness improved and where it still falls short.

## Completed Milestones

- v1.0 Bug Fix & Stability — phases 1-9, shipped 2026-03-31
- v1.1 Testing & QA — phases 10-12, shipped 2026-03-31
- v1.2 Price History — phases 13-18, shipped 2026-04-01
- v1.3 Performance & Optimization — phases 19-20, shipped 2026-04-01
- v1.4 Proxy Centralization — phases 21-23, shipped 2026-04-01
- v1.5 History Search & Polish — phases 24-26, shipped 2026-04-01
- v1.6 Green Scraper Robustness — phases 27-28, shipped 2026-04-02
- v1.7 Categories & Subgroups — phases 29-33, shipped 2026-04-03
- v1.8 History Search Completeness — phases 34-35, shipped 2026-04-04

## Next Up

- **Phase 37: Catalog Merge & Backfill** — merge Phase 36 discovery output into local catalog artifacts safely.
- Run `$gsd-discuss-phase 37` or `$gsd-plan-phase 37`.

## Progress

| Phase | Milestone | Status | Completed |
|-------|-----------|--------|-----------|
| 1-9 | v1.0 | ✅ Complete | 2026-03-31 |
| 10-12 | v1.1 | ✅ Complete | 2026-03-31 |
| 13-18 | v1.2 | ✅ Complete | 2026-04-01 |
| 19-20 | v1.3 | ✅ Complete | 2026-04-01 |
| 21-23 | v1.4 | ✅ Complete | 2026-04-01 |
| 24-26 | v1.5 | ✅ Complete | 2026-04-01 |
| 27-28 | v1.6 | ✅ Complete | 2026-04-02 |
| 29-33 | v1.7 | ✅ Complete | 2026-04-03 |
| 34 | v1.8 | ✅ Complete | 2026-04-04 |
| 35 | v1.8 | ✅ Complete | 2026-04-04 |
| 36 | v1.9 | ✅ Complete | 2026-04-04 |
| 37 | v1.9 | ⏳ Not started | - |
| 38 | v1.9 | ⏳ Not started | - |

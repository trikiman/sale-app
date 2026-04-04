# Roadmap: VkusVill Sale Monitor

**Created:** 2026-03-30
**Updated:** 2026-04-03
**Status:** Active milestone v1.8 — History Search Completeness

## Milestones

- ✅ **v1.0 Bug Fix & Stability** — Phases 1-9 (shipped 2026-03-31)
- ✅ **v1.1 Testing & QA** — Phases 10-12 (shipped 2026-03-31)
- ✅ **v1.2 Price History** — Phases 13-18 (shipped 2026-04-01)
- ✅ **v1.3 Performance & Optimization** — Phases 19-20 (shipped 2026-04-01)
- ✅ **v1.4 Proxy Centralization** — Phases 21-23 (shipped 2026-04-01)
- ✅ **v1.5 History Search & Polish** — Phases 24-26 (shipped 2026-04-01)
- ✅ **v1.6 Green Scraper Robustness** — Phases 27-28 (shipped 2026-04-02)
- ✅ **v1.7 Categories & Subgroups** — Phases 29-33 (shipped 2026-04-03)
- 🚧 **v1.8 History Search Completeness** — Phases 34-35 (planned 2026-04-03)

## Active Milestone: v1.8 History Search Completeness

**Goal:** Make History search show the full local catalog for a query, including live sale items and catalog products with no sale history yet.

**2 phases** | **6 requirements mapped** | All covered ✓

- [x] **Phase 34: History Search Backend Semantics** — Make search intentionally query across the local catalog without history-only exclusions. (completed 2026-04-04)
- [ ] **Phase 35: Search Result UX & Regression Coverage** — Make mixed-result states obvious and keep them protected by tests.

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 34 | History Search Backend Semantics | Make search intentionally query across the local catalog without history-only exclusions. | HIST-05, HIST-06, HIST-07 | 4 |
| 35 | Search Result UX & Regression Coverage | Make mixed-result states obvious and keep them protected by tests. | UI-14, UI-15, QA-01 | 4 |

### Phase 34: History Search Backend Semantics

**Goal:** Make the History API and search-mode filtering behave like an intentional catalog search instead of a history-only list with a text box.
**Requirements:** HIST-05, HIST-06, HIST-07
**Depends on:** —
**Plans:** 3/3 plans complete
**Success Criteria**:
1. Searching for a product that is currently on sale returns that product in History results.
2. Searching for a catalog product with zero sale history returns a result card instead of disappearing.
3. Search-mode filters and chip scope do not reintroduce `total_sale_count > 0`-style restrictions.
4. The search-mode contract is verified against mixed live-sale, history-only, and catalog-only fixtures.

### Phase 35: Search Result UX & Regression Coverage

**Goal:** Make mixed search results understandable to users and hard to regress.
**Requirements:** UI-14, UI-15, QA-01
**Depends on:** Phase 34
**Plans:** 2 plans
**Success Criteria**:
1. Search results clearly distinguish live sale, history-only, and no-history catalog matches.
2. Catalog-only search matches render with intentional "no data yet" presentation instead of looking broken.
3. Automated coverage exercises live-sale, history-only, and catalog-only search cases.
4. Search empty states and counts remain correct when search and filters are combined.

## Completed Milestones

- v1.0 Bug Fix & Stability — phases 1-9, shipped 2026-03-31
- v1.1 Testing & QA — phases 10-12, shipped 2026-03-31
- v1.2 Price History — phases 13-18, shipped 2026-04-01
- v1.3 Performance & Optimization — phases 19-20, shipped 2026-04-01
- v1.4 Proxy Centralization — phases 21-23, shipped 2026-04-01
- v1.5 History Search & Polish — phases 24-26, shipped 2026-04-01
- v1.6 Green Scraper Robustness — phases 27-28, shipped 2026-04-02
- v1.7 Categories & Subgroups — phases 29-33, shipped 2026-04-03

## Next Up

- **Phase 35: Search Result UX & Regression Coverage** — make mixed-result states obvious and keep them protected by tests.
- Start with `$gsd-discuss-phase 35` or jump straight to `$gsd-plan-phase 35`.

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
| 35 | v1.8 | 🟡 Planned | — |

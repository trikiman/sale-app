# Roadmap: VkusVill Sale Monitor

**Created:** 2026-03-30
**Updated:** 2026-04-06
**Status:** v1.11 planned — ready for phase kickoff

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
- ✅ **v1.9 Catalog Coverage Expansion** — Phases 36-38 (shipped 2026-04-04)
- ✅ **v1.10 Scraper Freshness & Reliability** — Phases 39-42 (shipped 2026-04-05)
- 🟡 **v1.11 Cart Responsiveness & Truth Recovery** — Phases 43-45 (planned 2026-04-06)

## Current Milestone: v1.11 Cart Responsiveness & Truth Recovery

**Goal:** Make add-to-cart feel fast and trustworthy by capping the click-path wait at 5 seconds, moving ambiguous recovery off the main interaction path, and tightening diagnostics around slow cart actions.

**3 phases** | **9 requirements mapped** | All covered ✓

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 43 | Backend Cart Response Contract | Bound the cart-add request path and preserve enough state for later reconciliation instead of chaining long inline recovery waits. | Complete    | 2026-04-06 |
| 44 | Frontend Bounded Add UX | End the visible add flow within 5 seconds, switch unresolved adds into a clear background-checking state, and prevent duplicate taps. | Complete    | 2026-04-06 |
| 45 | Cart Diagnostics & Verification | Make slow/ambiguous add outcomes inspectable and lock the new latency contract with repeatable regression coverage. | Complete    | 2026-04-06 |

### Phase 43: Backend Cart Response Contract

**Goal:** Bound backend cart-add latency and move ambiguous truth recovery off the main request path without losing eventual correctness.
**Requirements:** CART-06, CART-09
**Depends on:** —
**Plans:** 3/3 plans complete
**Success Criteria**:
1. Cart add no longer chains multi-second inline recovery loops before returning a response.
2. Backend returns a bounded ambiguous/pending outcome when upstream add truth is still unknown instead of stretching the visible wait path.
3. Enough attempt context is preserved to reconcile late-success cart adds after the initial response.
4. True backend failures remain distinguishable from ambiguous upstream slowdowns.

### Phase 44: Frontend Bounded Add UX

**Goal:** Cap the visible add-to-cart interaction at 5 seconds and keep the MiniApp interactive while reconciliation continues in the background.
**Requirements:** CART-04, UI-19, CART-05, CART-07, CART-08
**Depends on:** Phase 43
**Plans:** 3/3 plans complete
**Success Criteria**:
1. The add spinner or equivalent loading state stops at or before 5.0 seconds and switches to an explicit background-checking message.
2. Product browsing, filters, scrolling, and other controls remain usable while reconciliation continues.
3. Ambiguous add results do not render as hard failure or sold-out removal until reconciliation proves the add truly failed.
4. Repeated taps while one add attempt is unresolved do not send duplicate add requests.

### Phase 45: Cart Diagnostics & Verification

**Goal:** Expose slow cart-action behavior clearly enough to debug and verify the new bounded-latency contract end to end.
**Requirements:** OPS-04, QA-04
**Depends on:** Phases 43-44
**Plans:** 3/3 plans complete
**Success Criteria**:
1. Logs or admin diagnostics show cart-add latency segments, timeout class, and final reconciliation outcome for slow actions.
2. Automated coverage exercises fast success, ambiguous timeout with late success, and true failure paths.
3. Verification proves the visible add interaction stays within the 5-second UX budget even when reconciliation continues afterward.
4. The milestone ships with a repeatable verification path for the cart-response contract.

## Latest Completed Milestone: v1.10 Scraper Freshness & Reliability

Archived details: `.planning/milestones/v1.10-ROADMAP.md`

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
- v1.9 Catalog Coverage Expansion — phases 36-38, shipped 2026-04-04
- v1.10 Scraper Freshness & Reliability — phases 39-42, shipped 2026-04-05

## Next Up

- `$gsd-complete-milestone` — archive v1.11 and prepare the next milestone

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
| 34-35 | v1.8 | ✅ Complete | 2026-04-04 |
| 36-38 | v1.9 | ✅ Complete | 2026-04-04 |
| 39-42 | v1.10 | ✅ Complete | 2026-04-05 |
| 43 | v1.11 | ✅ Complete | 2026-04-06 |
| 44 | v1.11 | ✅ Complete | 2026-04-06 |
| 45 | v1.11 | ✅ Complete | 2026-04-06 |

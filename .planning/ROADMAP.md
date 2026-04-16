# Roadmap — VkusVill Sale Monitor

## Milestones

- ✅ **v1.0** Bug Fix & Stability — Phases 1-9 (shipped 2026-03-31)
- ✅ **v1.1** Testing & QA — Phases 10-12 (shipped 2026-03-31)
- ✅ **v1.2** Price History — Phases 13-18 (shipped 2026-04-01)
- ✅ **v1.3** Performance & Optimization — Phases 19-20 (shipped 2026-04-01)
- ✅ **v1.4** Proxy Centralization — Phases 21-23 (shipped 2026-04-01)
- ✅ **v1.5** History Search & Polish — Phases 24-26 (shipped 2026-04-01)
- ✅ **v1.6** Green Scraper Robustness — Phases 27-28 (shipped 2026-04-02)
- ✅ **v1.7** Categories & Subgroups — Phases 29-33 (shipped 2026-04-03)
- ✅ **v1.8** History Search Completeness — Phases 34-35 (shipped 2026-04-04)
- ✅ **v1.9** Catalog Coverage Expansion — Phases 36-38 (shipped 2026-04-04)
- ✅ **v1.10** Scraper Freshness & Reliability — Phases 39-42 (shipped 2026-04-05)
- ✅ **v1.11** Cart Responsiveness & Truth Recovery — Phases 43-45 (shipped 2026-04-06)
- ✅ **v1.12** Add-to-Cart 5s Hard Cap — Phase 46 (shipped 2026-04-08)
- [ ] **v1.13** Instant Cart & Reliability — Phases 47-51

## v1.13 Instant Cart & Reliability

**Goal:** Make add-to-cart feel instant with optimistic UI and fix current failures so cart adds actually succeed.
**Granularity:** Fine
**Phases:** 5 (47-51)
**Requirements:** 8

### Phases

- [ ] **Phase 47: Diagnose & Fix Cart Failures** - Reliable cart-add backend with structured error classification and diagnostic logging
- [x] **Phase 48: Session Warmup Optimization** - Pre-cache sessid/user_id so first cart add skips blocking warmup, real API confirm under 5s (completed 2026-04-11)
- [x] **Phase 49: Error Recovery & Polish** - Actionable error messages with session-expired redirect and retry capability (completed 2026-04-12)
- [x] **Phase 50: Requirements Formalization** - Define orphaned requirement IDs in REQUIREMENTS.md (gap closure) (completed 2026-04-16)
- [ ] **Phase 51: Cart Optimistic State Verification** - Verify quantity stepper and optimistic state fixes on production (gap closure)

### Phase Details

### Phase 47: Diagnose & Fix Cart Failures
**Goal**: Cart adds succeed reliably and failures produce structured diagnostic data
**Depends on**: Nothing (first phase)
**Requirements**: CART-15, CART-16
**Success Criteria** (what must be TRUE):
  1. User can tap add-to-cart and the product actually appears in their VkusVill cart
  2. When cart add fails, backend logs show the specific root cause (expired sessid, proxy failure, API change, etc.)
  3. Cart-add endpoint returns a typed error_type field (auth_expired, product_gone, transient, etc.) instead of generic 500
**Plans:** 2 plans
Plans:
- [ ] 47-01-PLAN.md — SSH diagnose production failure, fix root cause in vkusvill_api.py
- [ ] 47-02-PLAN.md — Propagate error_type through endpoint, add unit tests

### Phase 48: Session Warmup Optimization
**Goal**: First cart add is fast because session metadata is already cached; real API confirmation under 5s
**Depends on**: Phase 47
**Requirements**: PERF-01, PERF-02
**Success Criteria** (what must be TRUE):
  1. On app load, sessid and user_id are pre-extracted and cached so no warmup GET blocks the first cart add
  2. Cart add completes with real VkusVill API confirmation in under 5 seconds end-to-end
  3. Stale sessid (older than 30 min) is auto-refreshed before it causes a cart failure
**Plans**: TBD

### Phase 49: Error Recovery & Polish
**Goal**: Users see actionable error messages and can recover from failures without confusion
**Depends on**: Phase 48
**Requirements**: ERR-01, ERR-02
**Success Criteria** (what must be TRUE):
  1. User sees distinct messages for sold-out, session-expired, VkusVill-down, and network-error states
  2. Session-expired errors show a re-login prompt instead of a generic cart error
  3. After a transient error, user can retry the add without refreshing the page
**Plans**: TBD
**UI hint**: yes

### Phase 50: Requirements Formalization
**Goal**: Define all orphaned v1.13 requirement IDs (CART-15, CART-16, PERF-01, PERF-02, ERR-01, ERR-02) in REQUIREMENTS.md with traceability
**Depends on**: Phases 47-49
**Requirements**: CART-15, CART-16, PERF-01, PERF-02, ERR-01, ERR-02
**Gap Closure**: Closes 6 orphaned requirements from v1.13 audit
**Success Criteria** (what must be TRUE):
  1. All 6 requirement IDs have formal definitions in REQUIREMENTS.md
  2. Traceability table maps each requirement to its implementing phase
**Plans**: 1 plan

### Phase 51: Cart Optimistic State Verification
**Goal**: Verify cart-add → quantity stepper flow works end-to-end on production after source_unavailable fix
**Depends on**: Phase 50
**Requirements**: CART-17, CART-18
**Gap Closure**: Closes 1 integration gap (optimistic state overwrite) and 1 flow gap (quantity stepper)
**Success Criteria** (what must be TRUE):
  1. After cart-add success, the quantity stepper (CartQuantityControl) appears on the product card
  2. refreshCartState does not overwrite optimistic cart items when backend returns source_unavailable
  3. Post-milestone timeout/CSS/auth fixes verified on production
**Plans**: 1 plan

### Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 47. Diagnose & Fix Cart Failures | 2/2 | Complete | 2026-04-11 |
| 48. Session Warmup Optimization | 2/2 | Complete | 2026-04-12 |
| 49. Error Recovery & Polish | 1/1 | Complete | 2026-04-12 |
| 50. Requirements Formalization | 1/1 | Complete   | 2026-04-16 |
| 51. Cart Optimistic State Verification | 0/1 | Not started | - |

## Archives

See `.planning/milestones/v{X.Y}-ROADMAP.md` for full phase details of each milestone.

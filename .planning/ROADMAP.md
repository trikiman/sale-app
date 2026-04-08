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
- [ ] **v1.13** Instant Cart & Reliability — Phases 47-50

## v1.13 Instant Cart & Reliability

**Goal:** Make add-to-cart feel instant with optimistic UI and fix current failures so cart adds actually succeed.
**Granularity:** Fine
**Phases:** 4 (47-50)
**Requirements:** 9

### Phases

- [ ] **Phase 47: Diagnose & Fix Cart Failures** - Reliable cart-add backend with structured error classification and diagnostic logging
- [ ] **Phase 48: Session Warmup Optimization** - Pre-cache sessid/user_id so first cart add skips blocking warmup
- [ ] **Phase 49: Optimistic Cart UX** - Instant visual feedback on tap with background confirmation and rollback
- [ ] **Phase 50: Error Recovery & Polish** - Actionable error messages with session-expired redirect and retry capability

### Phase Details

### Phase 47: Diagnose & Fix Cart Failures
**Goal**: Cart adds succeed reliably and failures produce structured diagnostic data
**Depends on**: Nothing (first phase)
**Requirements**: CART-15, CART-16
**Success Criteria** (what must be TRUE):
  1. User can tap add-to-cart and the product actually appears in their VkusVill cart
  2. When cart add fails, backend logs show the specific root cause (expired sessid, proxy failure, API change, etc.)
  3. Cart-add endpoint returns a typed error_type field (auth_expired, product_gone, transient, etc.) instead of generic 500
**Plans**: TBD

### Phase 48: Session Warmup Optimization
**Goal**: First cart add is fast because session metadata is already cached
**Depends on**: Phase 47
**Requirements**: PERF-01, PERF-02
**Success Criteria** (what must be TRUE):
  1. On app load, sessid and user_id are pre-extracted and cached so no warmup GET blocks the first cart add
  2. Cart add hot path completes end-to-end in under 5 seconds including VkusVill API response
  3. Stale sessid (older than 30 min) is auto-refreshed before it causes a cart failure
**Plans**: TBD

### Phase 49: Optimistic Cart UX
**Goal**: User sees instant success feedback on tap without waiting for API response
**Depends on**: Phase 48
**Requirements**: UX-20, UX-21, UX-22
**Success Criteria** (what must be TRUE):
  1. User taps add-to-cart and immediately sees checkmark + updated cart count (before API responds)
  2. If background API call fails, the optimistic state reverts and user sees a brief error toast
  3. After a revert, the button returns to tappable add state within 2 seconds
  4. Optimistic cart count stays accurate across multiple rapid adds of different products
**Plans**: TBD
**UI hint**: yes

### Phase 50: Error Recovery & Polish
**Goal**: Users see actionable error messages and can recover from failures without confusion
**Depends on**: Phase 49
**Requirements**: ERR-01, ERR-02
**Success Criteria** (what must be TRUE):
  1. User sees distinct messages for sold-out, session-expired, VkusVill-down, and network-error states
  2. Session-expired errors show a re-login prompt instead of a generic cart error
  3. After a transient error, user can retry the add without refreshing the page
**Plans**: TBD
**UI hint**: yes

### Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 47. Diagnose & Fix Cart Failures | 0/? | Not started | - |
| 48. Session Warmup Optimization | 0/? | Not started | - |
| 49. Optimistic Cart UX | 0/? | Not started | - |
| 50. Error Recovery & Polish | 0/? | Not started | - |

## Archives

See `.planning/milestones/v{X.Y}-ROADMAP.md` for full phase details of each milestone.

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
- ✅ **v1.13** Instant Cart & Reliability — Phases 47-51 (shipped 2026-04-16, retroactively closed 2026-04-22 after v1.14 live verification)
- ✅ **v1.14** Cart Truth & History Semantics — Phases 52-55 (shipped and closed 2026-04-21, archived 2026-04-22)
- ✅ **v1.15** Proxy Infrastructure Migration — Phase 56 (shipped and closed 2026-04-23 after EC2 rollout on `ubuntu@13.60.174.46`; systemd xray active, live cart-add of 76 items confirmed via scheduler)
- ✅ **v1.17** VLESS Timeout Hardening — Phase 57 (shipped and closed 2026-04-25 after EC2 redeploy; `policy` + `observatory` + `leastPing` live in `bin/xray/configs/active.json`, 5/5 RU egress confirmed, Vercel miniapp `/api/cart/add` returns HTTP 200 with `success=true` ×2)

## v1.17 VLESS Timeout Hardening (SHIPPED 2026-04-25)

Follow-up to v1.15/v1.16. Fixed three root causes for the
"middle-of-cart-add timeout" bug reported by the user after the v1.15
rollout:

1. xray config was missing the `policy` block → default `connIdle=300s`
   kept dead connections alive for 5 minutes. Now set to `connIdle=30s`,
   `handshake=8s`.
2. xray had no `observatory` → dead outbounds stayed in the random
   balancer forever. Now probed every 5 minutes via `probeURL`, balancer
   strategy switched to `leastPing`.
3. `remove_proxy("127.0.0.1:10808")` was a silent no-op. Now rotates
   via `mark_current_node_blocked`, breaking the hang-retry loop.

Plus timeout alignment in cart + backend for VLESS handshake cost (3-5s
observed) and restored egress geo-verification in admission probes
(v1.16 PR #7 had removed it, violating plan D-05). Phase 56's earlier
0/15 RU-egress caveat is now 5/5 RU.

Phase: `.planning/phases/57-vless-timeout-hardening/`
Inspection: `.planning/phases/56-vless-proxy-migration/INSPECTION-2026-04-23.md`
Verification: `.planning/phases/57-vless-timeout-hardening/57-VERIFICATION.md`

## v1.15 Proxy Infrastructure Migration

**Goal:** Replace the 0%-alive SOCKS5 proxy pool with VLESS+Reality via local xray-core bridge so scraper and cart-add traffic reliably exits from a Russian IP without depending on short-lived free SOCKS5 proxies.
**Granularity:** Coarse (architectural migration, single phase, multiple plans)
**Phases:** 1 (56)
**Requirements:** 5 (PROXY-06 through PROXY-10)

### Phases

- [x] **Phase 56: VLESS Proxy Migration** - Replace SOCKS5 proxy_manager with xray-core VLESS+Reality bridge, preserve public API via shim, archive legacy for rollback, daily refresh with 4h VkusVill quarantine *(completed 2026-04-23: code + systemd + scripts + docs + dev verification + rollback rehearsal + EC2 rollout with live cart-add evidence; transcript in 56-VERIFICATION.md)*

### Phase Details

### Phase 56: VLESS Proxy Migration
**Goal**: Route all VkusVill-facing traffic through a local xray-core SOCKS5 bridge that tunnels over VLESS+Reality to RU exit nodes, with a shim preserving `from proxy_manager import ProxyManager` so no business-logic code changes
**Depends on**: Nothing (architectural migration)
**Requirements**: PROXY-06, PROXY-07, PROXY-08, PROXY-09, PROXY-10
**Success Criteria** (what must be TRUE):
  1. [x] `from proxy_manager import ProxyManager` still works in all 7 production files and 3 test files — resolves to the new VLESS-backed implementation via a shim
  2. [x] xray-core runs on both local dev (Windows) and EC2 production (systemd), listening on `socks5://127.0.0.1:10808` *(dev verified; EC2 `saleapp-xray.service` active+running since 2026-04-23 05:22 MSK, managed binary at `/home/ubuntu/saleapp/bin/xray/current/xray` with config at `bin/xray/configs/active.json`, drop-in at `saleapp-scheduler.service.d/10-xray.conf` preserves the prod `xvfb-run` wrapper)*
  3. [x] A real VkusVill cart-add request succeeds through the bridge on production (live evidence, not code review) *(EC2 scheduler `scrape_green.py` on 2026-04-23 added 76/76 live items to VkusVill cart through xray bridge, reconciled via `basket_recalc` API; transcript in `.planning/phases/56-vless-proxy-migration/56-VERIFICATION.md` section "Check J Step 4/5")*
  4. [x] Daily refresh (fetch → parse → geo-filter RU → test nodes → rebuild xray config) completes in under 15 minutes, finds at least 5 alive RU exit nodes on average *(live test admitted 28 RU nodes in 5m21s)*
  5. [x] Failure classification routes VkusVill-specific blocks (ReadTimeout / 403 / 429 / 451 / content_mismatch) into the existing 4h cooldown and routes node-level failures (TLS handshake fail, outbound unreachable) into immediate permanent removal
  6. [x] Old SOCKS5 infrastructure is archived under `legacy/proxy-socks5/` (not deleted) and has a documented rollback procedure that restores it within one git operation *(rehearsed: `git revert cc70185` leaves pytest green at 167/2)*
**Plans:** 5 plans
Plans:
- [x] 56-01-PLAN.md — VLESS URL parser + xray config generator (pure Python, tested) (eceb5bd)
- [x] 56-02-PLAN.md — xray-core bootstrap + subprocess bridge (download, verify, manage lifecycle) (fdb64dc)
- [x] 56-03-PLAN.md — vless_manager.py as drop-in ProxyManager replacement (e32a7d9)
- [x] 56-04-PLAN.md — Archive old SOCKS5 infrastructure and install shim (cc70185)
- [x] 56-05-PLAN.md — Production verification on EC2 and rollback rehearsal (94826d9 deploy infra + verification evidence; 24b00b9 dev-box verification; 083d37f + `faf549e` hotfix; EC2 rollout completed 2026-04-23 with live cart-add evidence)

## v1.13 Instant Cart & Reliability

**Goal:** Make add-to-cart feel instant with optimistic UI and fix current failures so cart adds actually succeed.
**Granularity:** Fine
**Phases:** 5 (47-51)
**Requirements:** 8

### Phases

- [x] **Phase 47: Diagnose & Fix Cart Failures** - Reliable cart-add backend with structured error classification and diagnostic logging (completed 2026-04-11; live UAT closed via v1.14 phase 55)
- [x] **Phase 48: Session Warmup Optimization** - Pre-cache sessid/user_id so first cart add skips blocking warmup, real API confirm under 5s (completed 2026-04-11)
- [x] **Phase 49: Error Recovery & Polish** - Actionable error messages with session-expired redirect and retry capability (completed 2026-04-12)
- [x] **Phase 50: Requirements Formalization** - Define orphaned requirement IDs in REQUIREMENTS.md (gap closure)
 (completed 2026-04-16)
- [x] **Phase 51: Cart Optimistic State Verification** - Verify quantity stepper and optimistic state fixes on production (gap closure)
 (completed 2026-04-16)

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
| 51. Cart Optimistic State Verification | 1/1 | Complete   | 2026-04-16 |

## v1.14 Cart Truth & History Semantics

**Goal:** Make add-to-cart work in real user flows and make history/restock semantics reflect real sale transitions instead of fake reentries.
**Granularity:** Fine
**Phases:** 4 (52-55)
**Requirements:** 8

### Phases

- [x] **Phase 52: Real Cart Failure Reproduction & Diagnostics** - Reproduce the live MiniApp cart failure and capture enough evidence to stop guessing (completed 2026-04-21)
- [x] **Phase 53: Cart Truth Path Fixes** - Make add-to-cart and quantity-state transitions truth-backed end-to-end (completed 2026-04-21)
- [x] **Phase 54: History Reentry Semantics Correction** - Remove fake restocks/reentries from history, notifier, and session logic (completed 2026-04-21)
- [x] **Phase 55: Live Verification & Release Decision** - Verify cart and history behavior against fresh production-like evidence before closure (completed 2026-04-21)

### Phase Details

### Phase 52: Real Cart Failure Reproduction & Diagnostics
**Goal**: Reproduce the real user-facing add-to-cart failure and capture concrete backend/admin evidence for the failing path
**Depends on**: Nothing (first phase)
**Requirements**: OPS-05
**Success Criteria** (what must be TRUE):
  1. The broken add-to-cart flow is reproduced end-to-end from MiniApp interaction through backend/cart logs
  2. Admin/status or logs show exactly why the failing cart attempt was classified the way it was
  3. The next fix scope is based on observed failure evidence, not inferred code-path theory
**Plans**: TBD

### Phase 53: Cart Truth Path Fixes
**Goal**: Make MiniApp add-to-cart succeed reliably and keep frontend cart state aligned with confirmed cart truth
**Depends on**: Phase 52
**Requirements**: CART-19, CART-20, CART-21
**Success Criteria** (what must be TRUE):
  1. User can add a product from the MiniApp and the product actually appears in the real VkusVill cart
  2. Success and quantity-stepper UI only appear when backed by confirmed add/cart truth
  3. Ambiguous or failed add flows end in a truthful stable state with a clear retry/recovery path
**Plans**: TBD
**UI hint**: yes

### Phase 54: History Reentry Semantics Correction
**Goal**: Make history, notifier, and "new again" behavior reflect only true sale exits and true sale returns, and repair the already-corrupted current data
**Depends on**: Phase 53
**Requirements**: HIST-09, HIST-10, HIST-11
**Success Criteria** (what must be TRUE):
  1. Stale or missing scrape cycles do not create fake restocks or fake reentries
  2. Session reopening only happens when the product truly left sale and then returned
  3. User-visible history/notifier semantics distinguish continued sale from genuine return-to-sale events
  4. Existing persisted history/session records are repaired or rebuilt so current data no longer shows fake restocks/reentries
**Plans**: TBD

### Phase 55: Live Verification & Release Decision
**Goal**: Prove cart truth and corrected history semantics with fresh evidence before deciding whether the milestone can close
**Depends on**: Phase 54
**Requirements**: QA-05
**Success Criteria** (what must be TRUE):
  1. Verification includes a live or production-like proof that add-to-cart works for a real user path
  2. Verification includes evidence that fake restock/reentry behavior is no longer present in history semantics
  3. Milestone closure decision is based on fresh evidence, not only code review or inferred behavior
**Plans**: TBD

### Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 52. Real Cart Failure Reproduction & Diagnostics | 1/1 | Complete | 2026-04-21 |
| 53. Cart Truth Path Fixes | 1/1 | Complete | 2026-04-21 |
| 54. History Reentry Semantics Correction | 1/1 | Complete | 2026-04-21 |
| 55. Live Verification & Release Decision | 1/1 | Complete | 2026-04-21 |

## Archives

See `.planning/milestones/v{X.Y}-ROADMAP.md` for full phase details of each milestone.

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
- ✅ **v1.18** Geo Resolver & Scraper Recovery — Phase 58 (shipped and closed 2026-04-25; multi-provider geo resolver lifts pool 15 → 25 nodes, scraper survives Chromium CDP-WS HTTP 500 mid-cycle, miniapp cart-add still HTTP 200)
- ⏳ **v1.19** Production Reliability & 24/7 Uptime — Phases 59-61 (active, started 2026-05-03; corrected pre-flight VLESS probe + observatory probeURL alignment + graduated circuit breaker + unauthed deep health endpoint, all behind a per-phase EC2 smoke verification gate)

## v1.19 Production Reliability & 24/7 Uptime (ACTIVE — started 2026-05-03)

Close the production drift exposed after v1.18 shipped: 8 days of degraded behavior visible only in EC2 logs (pool 25 → 13, 162 consecutive scraper-cycle failures, 30/30 detail-proxy timeouts) while Vercel `/api/products` returned HTTP 200 with cached data. PR #25 (Devin, 2026-04-29) attempted a 5 s pre-flight probe hotfix, was reverted 8 minutes later by PR #26 because empirical healthy-node latency through the bridge is 7-9 s.

The milestone is explicitly **robust-over-fast**: per user direction 2026-05-03, no fast hotfixes — every phase ships with a scripted EC2 smoke test (`scripts/verify_v1.19.sh`), a `VERIFICATION.md`, and a rehearsed rollback path. Backend reliability only; user-facing degraded mode (Category G) deferred to v1.20.

Full grounded analysis: `.planning/research/v1.19-SUMMARY.md`. Requirements: `.planning/REQUIREMENTS.md` (18 items: 12 REL, 3 OBS, 3 OPS).

**Goal:** Keep the VkusVill sale app continuously healthy from the user's perspective (Vercel frontend + Telegram MiniApp) 24/7 by hardening the EC2 data pipeline against post-v1.18 failure modes.
**Granularity:** Medium
**Phases:** 3 (59-61)
**Requirements:** 18 (REL-01..12, OBS-01..03, OPS-06..08)

### Phases

- [ ] **Phase 59: Corrected Pre-flight VLESS Probe** — Redo PR #25 with the lessons from PR #26's revert: 12 s timeout (not 5 s), cap rotations at 2 (not 5), prefer `leastPing` balancer rotation over Python-side `next_proxy()` to minimize xray restarts. Ships `vless/preflight.py::probe_bridge_alive`, regression test that fails if probe timeout drops below empirical p95, EC2 smoke test, and `scripts/verify_v1.19.sh` skeleton.
- [ ] **Phase 60: Observatory probeURL + Graduated Circuit Breaker** — Change xray `observatory.probeURL` from `google.com/generate_204` to a VkusVill endpoint so `leastPing` balancer reflects real-target reachability; replace the cycle-counter circuit breaker with a 3-state machine (closed → open → half_open) + exponential backoff capped at 30 min, persisted in `data/scheduler_state.json`. Adds breaker state transitions + probe URL regression test to `scripts/verify_v1.19.sh`.
- [ ] **Phase 61: Deep Health Endpoint + Pool Snapshot** — Mount unauthed `GET /api/health/deep` returning 200/503 based on pool size, breaker phase, cycle freshness, xray process state, and merged-products mtime; add `VlessProxyManager.pool_snapshot()` accessor; extend `/admin/status` with the same `reliability` block. Adds external-curl-from-outside-EC2 to smoke script. Verifies pool drain trend visibility (REL-11/12).

### Phase Details

### Phase 59: Corrected Pre-flight VLESS Probe
**Goal:** Detect a silently-degraded VLESS exit before the scheduler spends 30-45 s launching Chrome only to fail at page load — using the lessons from PR #25 → PR #26 revert (12 s timeout, cap 2 rotations, prefer balancer over Python-side removal).
**Depends on:** Phase 58 (v1.18) shipped state — VLESS bridge is operational, just silently degrading; no breaking changes to the bridge itself in this phase.
**Requirements:** REL-01, REL-02, REL-03, REL-04, REL-05 — plus the first concrete instances of OPS-06 (per-phase VERIFICATION.md), OPS-07 (smoke script foundation), OPS-08 (rollback rehearsal).
**Success Criteria** (what must be TRUE):
  1. [ ] `vless/preflight.py::probe_bridge_alive(timeout=12)` exists, returns a typed `ProbeResult`, and is called from `scheduler_service.py::_run_scraper_set` before each `scrape_*.py` launch.
  2. [ ] Probe timeout = 12 s is guarded by a regression test (`tests/test_preflight_timeout_regression.py`) that fails if anyone lowers the constant below the measured EC2 healthy-node p95 + 30% margin.
  3. [ ] Pre-flight rotation is capped at 2 attempts per scraper launch — verified by an integration test that simulates probe failure and asserts at most 2 `_remove_host_and_restart` calls per launch.
  4. [ ] Live verification on EC2: a deliberately-bad single proxy in the pool causes one rotation + recovery within ≤ 30 s, instead of 5 cascading xray restarts (PR #25 failure mode).
  5. [ ] `scripts/verify_v1.19.sh` exists and reports pass/fail for the 4 criteria above; run from local terminal via SSH; idempotent.
  6. [ ] Vercel miniapp `/api/cart/add` returns HTTP 200 with `success=true` post-deploy (no regression on v1.18).
**Plans:** TBD via `/gsd-plan-phase 59`

### Phase 60: Observatory probeURL + Graduated Circuit Breaker
**Goal:** Fix the silent killer (xray observatory probes Google but our traffic goes to VkusVill, so blocked-by-VkusVill nodes stay "fast" in `leastPing`) AND give the scheduler a real recovery path (3-state breaker + exponential backoff) instead of 162 useless re-trips.
**Depends on:** Phase 59 (smoke script foundation needed for verification).
**Requirements:** REL-06, REL-07, REL-08, REL-09, REL-10 — plus continued OPS-06/07/08.
**Success Criteria:**
  1. [ ] `vless/config_gen.py::build_xray_config` emits `observatory.probeURL = "https://vkusvill.ru/favicon.ico"` (or operator-confirmed VkusVill stable endpoint); regression test asserts the configured probeURL hostname matches `*.vkusvill.ru`.
  2. [ ] `scheduler/breaker.py::CircuitBreaker` exists with phases {`closed`, `open`, `half_open`}; transitions: 3 consecutive failed cycles → open; cooldown elapsed → half_open; half-open probe succeeds → closed; half-open probe fails → open with `backoff_level += 1`.
  3. [ ] Cooldown follows `min(120 * 2^level, 1800)` (cap 30 min); unit tests cover all level transitions.
  4. [ ] Counter resets to 0 on **any** successful scraper run (current behavior only resets on fully-clean cycle); integration test simulates 2-of-3 failures for 5 cycles and asserts breaker does not trip while ≥1 scraper succeeds, AND asserts breaker tracks per-scraper failure separately for visibility.
  5. [ ] `data/scheduler_state.json` persists breaker state across restart; corrupt-file fallback test passes.
  6. [ ] Live verification on EC2: deliberately force all 3 scrapers to fail for 3 cycles, observe `closed → open → cooldown 120s → half_open → green-only probe → recovery`; total recovery time ≤ 5 min vs. current 5.4 h.
**Plans:** TBD via `/gsd-plan-phase 60`

### Phase 61: Deep Health Endpoint + Pool Snapshot
**Goal:** Expose stack health truthfully via an unauth `/api/health/deep` endpoint suitable for external uptime ping services, with a `reasons[]` array for post-incident debugging; add pool-size trend logging so multi-day drift (pool 25 → 13) is visible without log scraping.
**Depends on:** Phase 60 (breaker state file is part of the response).
**Requirements:** REL-11, REL-12, OBS-01, OBS-02, OBS-03 — plus continued OPS-06/07/08.
**Success Criteria:**
  1. [ ] `GET /api/health/deep` (no auth) returns HTTP 200 + JSON when healthy and HTTP 503 + JSON when degraded/unhealthy; response shape matches schema in `.planning/research/v1.19-ARCHITECTURE.md` §4; rate-limited 1 req/s/IP.
  2. [ ] Healthy criteria match REQUIREMENTS.md OBS-02 (all-of: pool_size ≥ MIN_HEALTHY, breaker ∈ {closed, half_open}, last successful cycle ≤ 15 min ago, xray running, products.json mtime ≤ 15 min); response always includes `status` and `reasons[]`.
  3. [ ] No node IPs, no user identifiers, no cookie state in the unauth response (privacy review checked into the verify script).
  4. [ ] `VlessProxyManager.pool_snapshot()` returns `{size, min_healthy, quarantined_count, active_outbounds, last_refresh_at}`; `/admin/status` exposes a `reliability` block with breaker + pool snapshot for the operator view.
  5. [ ] `proxy_events.jsonl` gains `pool_size`, `quarantined_count`, `active_outbounds_count` on every refresh and quarantine event; verification queries the file and asserts trend visibility over a 24 h window.
  6. [ ] External `curl https://vkusvillsale.vercel.app/api/health/deep` from a non-EC2 host returns 200 when stack is healthy and 503 when synthetically degraded (e.g. xray paused).
**Plans:** TBD via `/gsd-plan-phase 61`

## v1.18 Geo Resolver & Scraper Recovery (SHIPPED 2026-04-25)

Closes the two known issues punted from v1.17 (`57-VERIFICATION.md`):

1. **ipinfo.io rate-limiting** — single-provider `verify_egress` saw ~70% HTTP 429s during refresh, capping the admitted pool well below upstream availability. `vless/xray.py` now iterates a 3-provider chain (ipinfo.io → ipapi.co → ip-api.com); `vless/manager.py::_probe_one` drops the explicit `url=` kwarg so refresh probes use the chain.
2. **Chromium CDP WebSocket HTTP 500 mid-scrape** — `scrape_green.py` crashed deterministically at "Step 2.9: Clearing unavailable items..." right after a force-reload (Chromium swapped the CDP target while we still held the old `page` handle). Three new helpers (`_is_dead_ws_error`, `_refresh_page_handle`, `_safe_js`) plus `_navigate_and_settle` detect the dead WebSocket and re-acquire a fresh tab handle, falling through to `browser.get(url)` only when no live tab is recoverable.

Live evidence (2026-04-25, on `ubuntu@13.60.174.46`):

| Metric | v1.17 | v1.18 |
|---|---|---|
| Pool size after refresh | 15 nodes | **25 nodes** (+67%) |
| Active outbounds in `active.json` | 16 | 27 |
| `policy.handshake / connIdle` | 8s / 30s | 8s / 30s (unchanged) |
| Balancer strategy | `leastPing` | `leastPing` (unchanged) |
| Geo provider chain | ipinfo.io only | ipinfo.io → ipapi.co → ip-api.com |
| Scraper recovery helpers | absent | `_is_dead_ws_error`, `_refresh_page_handle`, `_safe_js`, `_navigate_and_settle` present |
| Vercel miniapp `/api/cart/add` | HTTP 200, `success=true` | **HTTP 200, `success=true, cart_items=3, cart_total=971.6`** |
| `verify_egress(country='RU')` through bridge | RU | RU (multi-provider AND single-provider both confirm) |

PRs: #17 (58-01), #18 (58-02), #19 (58-03 deploy + verify + docs).

**Goal:** Lift the v1.17 VLESS pool ceiling and harden the green scraper against Chromium CDP-WebSocket HTTP 500 mid-cycle.
**Granularity:** Fine
**Phases:** 1 (58)
**Requirements:** n/a (operational hardening; tracked via phase 58 README success criteria)

### Phases

- [x] **Phase 58: Geo Resolver & Scraper Recovery** - Multi-provider geo resolver chain (ipinfo.io → ipapi.co → ip-api.com) lifts pool 15 → 25 nodes; `scrape_green.py` survives Chromium CDP-WebSocket HTTP 500 via 4 new helpers *(completed 2026-04-25: 58-01 PR #17 `acf8929`, 58-02 PR #18 `f616af9`, 58-03 PR #19; tests grew 96 → 111 in `tests/`, Vercel miniapp `/api/cart/add` returns HTTP 200)*

### Phase Details

### Phase 58: Geo Resolver & Scraper Recovery
**Goal**: Close the two known issues punted from v1.17 — ipinfo.io single-provider rate-limiting capping pool admission, and Chromium CDP-WebSocket HTTP 500 crashing `scrape_green.py` mid-cycle
**Depends on**: Phase 57 (v1.17)
**Requirements**: n/a (operational hardening)
**Success Criteria** (what must be TRUE):
  1. [x] Pool size after refresh on EC2 ≥ 15 (v1.17 baseline) *(achieved: 25 nodes, +67%)*
  2. [x] `XrayProcess._GEO_PROVIDERS` exposes all three providers; live `verify_egress` returns `RU` through the chain
  3. [x] `scrape_green.py` exposes 4 recovery helpers (`_is_dead_ws_error`, `_refresh_page_handle`, `_safe_js`, `_navigate_and_settle`) as module-level callables
  4. [x] Vercel miniapp `/api/cart/add` still returns HTTP 200 with `success=true` (no regression on v1.17 fix) *(achieved: `cart_items=3, cart_total=971.6`)*
  5. [x] All existing tests still pass; new tests cover the helpers *(achieved: `tests/` 96 → 111, `backend/` 86/86, 2 skipped live-only unchanged)*
**Plans:** 3 plans
Plans:
- [x] 58-01-PLAN.md — Multi-provider geo resolver in `vless/xray.py::verify_egress` + `vless/manager.py::_probe_one` call site (PR #17, `acf8929`)
- [x] 58-02-PLAN.md — Scraper CDP-WS recovery helpers in `scrape_green.py` (PR #18, `f616af9`)
- [x] 58-03-PLAN.md — Deploy + verify scripts + ROADMAP update + docs (PR #19)

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

**Goal:** Resolve the post-v1.15 "middle-of-cart-add timeout" bug by fixing 3 P0 root causes (xray policy, observatory + leastPing, `remove_proxy` no-op) and 5 symptom bugs (timeouts, geo verification regression).
**Granularity:** Fine
**Phases:** 1 (57)
**Requirements:** n/a (hardening; preserves PROXY-06…PROXY-10 from v1.15)

### Phases

- [x] **Phase 57: VLESS Timeout Hardening** - xray `policy` (`connIdle=30s`, `handshake=8s`) + `observatory` + `leastPing`, Python timeout alignment, `remove_proxy` rotation, restored egress geo-verification *(completed 2026-04-25: 57-01 `d92ddca` PR #13, 57-02 `ef50253` PR #14, 57-03 `4e53817` PR #15, 57-04 deploy + live verify; egress 0/15 → 5/5 RU; Vercel miniapp `/api/cart/add` HTTP 200 ×2)*

### Phase Details

### Phase 57: VLESS Timeout Hardening
**Goal**: Eliminate the mid-connection timeout failure mode by fixing the 3 P0 root causes (R1 missing xray policy, R2 missing observatory + random balancer, R3 `remove_proxy` no-op) plus 5 symptom bugs (timeout alignment, geo verification regression, retry loop)
**Depends on**: Phase 56 (v1.15)
**Requirements**: n/a (preserves PROXY-06…PROXY-10)
**Success Criteria** (what must be TRUE):
  1. [x] `bin/xray/configs/active.json` contains `policy` (`connIdle=30s`, `handshake=8s`), `observatory` (probe every 5 min via `generate_204`), and `routing.balancers[].strategy=leastPing`
  2. [x] `curl -x socks5h://127.0.0.1:10808 https://ipinfo.io/json` through the bridge returns an RU country (egress geo-verification restored)
  3. [x] Admitted pool size after refresh ≥ 7 RU-verified nodes (no longer mixed-egress)
  4. [x] Vercel miniapp `/api/cart/add` returns HTTP 200 with `success=true` *(achieved: HTTP 200 ×2, was skipped in v1.15)*
  5. [x] `pytest -v` passes on full suite (`tests/` 96 + `backend/` 86 + 2 skipped live-only)
  6. [x] All 4 sub-plans land as atomic commits matching their PLAN-template subject lines
**Plans:** 4 plans
Plans:
- [x] 57-01-PLAN.md — xray `policy` block + `observatory` + `leastPing` balancer (PR #13, `d92ddca`)
- [x] 57-02-PLAN.md — Python timeout alignment + `remove_proxy` rotate (PR #14, `ef50253`)
- [x] 57-03-PLAN.md — Restore egress geo-verification in admission probe (PR #15, `4e53817`)
- [x] 57-04-PLAN.md — Deploy scripts + EC2 verification + docs (`57-VERIFICATION.md`)

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

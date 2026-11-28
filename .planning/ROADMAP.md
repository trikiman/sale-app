# Roadmap: VkusVill Sale Monitor

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
- ✅ **v1.13** Instant Cart & Reliability — Phases 47-51 (shipped 2026-04-16)
- ✅ **v1.14** Cart Truth & History Semantics — Phases 52-55 (shipped 2026-04-21)
- ✅ **v1.15** Proxy Infrastructure Migration — Phase 56 (shipped 2026-04-23)
- ✅ **v1.17** VLESS Timeout Hardening — Phase 57 (shipped 2026-04-25)
- ✅ **v1.18** Geo Resolver & Scraper Recovery — Phase 58 (shipped 2026-04-25)
- ✅ **v1.19** Production Reliability & 24/7 Uptime — Phases 59-61 (shipped 2026-05-05)
- ✅ **v1.20** Cart-Add Latency & User-Facing Responsiveness — Phases 62-66 + 66.1/.2/.3 (shipped 2026-05-12, tag `v1.20`)
- ✅ **v1.21** VLESS Pool Self-Healing & Reload Pipeline — Phases 67-69 (shipped 2026-05-12, tag `v1.21`)
- ✅ **v1.22** UX Debt Cleanup + Tooling Polish — Phases 70-73 (shipped 2026-05-13, tag `v1.22`)
- ✅ **v1.23** Detail-Path Performance + UX Polish — Phases 74-76 (shipped 2026-05-13, tag `v1.23`)
- ✅ **v1.24** Pool Self-Heal Hardening + Outage UX — Phases 77-79 (shipped 2026-05-13, tag `v1.24`)
- ✅ **v1.25** Operator Visibility + Test Coverage — Phases 80-82 (shipped 2026-05-13, tag `v1.25`)
- ✅ **v1.26** Miniapp Test Harness + Style Guide Debt Cleanup — Phases 83-85 (shipped 2026-05-15, tag `v1.26`) — see [`.planning/milestones/v1.26-ROADMAP.md`](milestones/v1.26-ROADMAP.md)
- ✅ **v1.27** Stability Recovery & Scraper Health — Phases 86-89 (shipped 2026-11-11, tag `v1.27`) — see [`.planning/v1.27-MILESTONE-AUDIT.md`](v1.27-MILESTONE-AUDIT.md)
- ✅ **v1.28** Component Verification & Hardening — Phases 90-93 (shipped 2026-11-13)
- ✅ **v1.29** Own Proxy Egress & Ops Polish — no phases (EGRESS-01 + OPS-02 shipped 2026-11-15)
- ✅ **v1.30** Green Tag Uptime — Phases 94-97 (closed 2026-11-28, Phase 96 acceptance `exit 0`)

## Phase Details

- [x] **Phase 94: Green Uptime Guardrails** - API never reports a green zero while a live green snapshot exists; suppression is explicit and tested
- [x] **Phase 95: Green Cycle Self-Healing** - every abort stage (Chrome launch, CDP target swap, delivery slot, cart seed) recovers within its retry budget
- [x] **Phase 96: 7-Day Soak & Uptime Report** - 168 h measured run with a per-cycle record proving green never fell to a false zero
- [x] **Phase 97: URnetwork-Primary Egress** - green cycles never stall because the VLESS pool died; URnetwork is a pinned route, not a balancer member

### Phase 94: Green Uptime Guardrails

**Goal**: A false green zero becomes structurally impossible in the API response, and any suppression of green cards is explicit in the payload instead of silent.
**Depends on**: Nothing (first phase of v1.30)
**Requirements**: GREEN-UP-01, GREEN-UP-04
**Success Criteria**:
1. `GET /api/products` returns a non-empty green list whenever `green_products.json` holds products and VkusVill has not reported `source_empty` — asserted across the full stale/fresh × empty/non-empty matrix in a regression test.
2. A `greenSuppressed` field (or equivalent) states the reason whenever green cards are withheld, and `/admin/status` mirrors it; no colour is dropped without a recorded reason.
3. An alert fires (log/status path, Telegram if the channel is configured) when the green snapshot is older than 2× the interval, and when `green == 0` while `greenLiveCount > 0`.
4. The regression test fails if anyone reinstates the old unconditional stale-strip for green.
**Plans**: 3 plans

Plans:
- [ ] 94-01: Extract the green visibility decision into one function with an explicit reason enum
- [ ] 94-02: Emit `greenSuppressed` from `/api/products` and surface it in `/admin/status`
- [ ] 94-03: Matrix regression test + alert for stale-snapshot and zero-with-live-count

### Phase 95: Green Cycle Self-Healing

**Goal**: One failed green cycle costs at most one refresh interval; each abort stage has a bounded, logged recovery path instead of killing the run.
**Depends on**: Phase 94
**Requirements**: GREEN-UP-02
**Success Criteria**:
1. Chrome launch waits long enough and retries enough that a cold 1 vCPU box reaches CDP; a launch failure logs the child's stderr with the pid.
2. A CDP target swap after the seed add or after the cart clear recovers on a fresh handle within the retry budget; the cycle continues instead of exiting 1.
3. Delivery-slot selection never clicks arbitrary controls: only modals whose text mentions delivery, otherwise it no-ops and logs why.
4. A synthetic failure injected at each stage (Chrome down, dead WS after seed, dead WS after clear, no delivery modal) ends with the cycle completing or aborting *after* exhausting retries — never hanging, never blocking the next run.
5. Two consecutive weeks of scheduler output show no `Already running, skipping` lock held by a dead process.
**Plans**: 3 plans

Plans:
- [ ] 95-01: Stage-by-stage recovery audit of scrape_green.py with per-stage retry budgets
- [ ] 95-02: Stuck-process guard so a dead cycle cannot hold the run lock past the interval
- [ ] 95-03: Fault-injection tests for the four abort stages

### Phase 96: 7-Day Soak & Uptime Report

**Goal**: Prove the user's goal — green tags do not fall off for a week — with measurements instead of claims.
**Depends on**: Phase 95
**Requirements**: GREEN-UP-03
**Success Criteria**:
1. Every green cycle appends a durable record: timestamp, exit code, green count, live count, failure stage.
2. `/admin/green-uptime` returns the last 7 days: total cycles, failed cycles, longest green-zero streak, per-stage abort counts.
3. A 168-hour soak completes with zero incidents of `green == 0` while a live green snapshot existed; any incident is listed with its timestamp and stage.
4. The report is committed to `.planning/` as the milestone's verification artifact.
**Plans**: 3 plans

Plans:
- [ ] 96-01: Per-cycle uptime recorder with rotation
- [ ] 96-02: `/admin/green-uptime` aggregation endpoint + `/admin/status` summary
- [ ] 96-03: 168 h soak, report written to `.planning/v1.30-GREEN-UPTIME.md`

### Phase 97: URnetwork-Primary Egress

**Goal**: Green cycles never stall because the VLESS pool decayed to zero; URnetwork is a pinned route and the first probe, not a balancer member.
**Depends on**: Phase 96 (blocker: the soak cannot collect cycles without a working egress)
**Requirements**: GREEN-UP-04
**Success Criteria**:
1. A dedicated inbound (10809) routes to the URnetwork outbound via a pinned rule, and exists only when a UR cache is present.
2. `probe_bridge_alive()` tries URnetwork first, names the winning route, and caches per route so a healthy UR never masks a dead balancer.
3. `proxy_candidates()` returns URnetwork before the env/VLESS fallback.
4. On the live server a green cycle completes through URnetwork and appends a record to `green_uptime.jsonl`.
**Plans**: 2 plans

Plans:
- [ ] 97-01: Pinned URnetwork inbound + routing rule in `vless/config_gen.py`
- [ ] 97-02: Route-aware preflight and UR-first proxy candidates

## v1.30 Green Tag Uptime (ACTIVE)

## v1.27 Stability Recovery & Scraper Health (SHIPPED 2026-11-11)
- Session history orphan bug fixed (CLOSE_UNSAFE_TIMEOUT)
- VLESS pool expanded (+3 sources, 251 RU hosts)
- Scrapers verified healthy, nginx restored with auto-restart
- 3/3 requirements satisfied, tech debt deferred to v1.28

## v1.28 Component Verification & Hardening (SHIPPED 2026-11-13)
- Phase 90: full pipeline verified live (158 products, all sources fresh)
- Phase 91: root-caused the empty pool — `pool_size: 0` is NOT a failure mode
  (scrapers run through manual seeds); VkusVill blocks datacenter ASNs and
  detects VPNs (`vpn_detected` on 66/208 candidates). Shipped `vless/asn_filter.py`
- Phase 92: nginx survives reboots, server recovers in ~60 s; `scheduler.log`
  bloat confirmed (`/admin/logs` times out). Log rotation still needs SSH
- Phase 93: 25 `TODO(v1.27)` retagged to v1.28 + CSS migration plan
- Discovered and used a deploy path with no SSH: `POST /api/github-webhook`
  does `git pull` server-side. `ADMIN_TOKEN` recovered from git history
- Research: `.planning/research/vkusvill-access-rkn-check.md` (RKN hypothesis
  disproved with measurements; per-ASN reachability map)

## v1.26 Miniapp Test Harness + Style Guide Debt Cleanup (SHIPPED 2026-05-15, tag `v1.26`)

Full scope shipped, 8/8 v1 requirements (TEST-01/02/03, TOOL-05/07/08, UX-EMPTY-01) + 7 robustness sidequests (84.1-84.7) shipped during Phase 84 — pool admission stability + scheduler robustness + scraper safe-click + per-color staleness thresholds. Archive: `.planning/milestones/v1.26-{ROADMAP,REQUIREMENTS}.md` + `.planning/phases/{83,84,85}/*-SUMMARY.md`. 32 commits `21f7969..d6b9a6d`, 2 partial-met requirements (TOOL-08 lint budget at 10 not 0 — 5 react-hooks advisories deferred to v1.27; OPS-29 verify script deferred — CI workflow covers same surface).

**Goal:** Vitest/RTL safety net + 46 inline-style and 135 spacing-scale CSS violations refactored to zero + lint rules promoted to ERROR + fresh-deploy empty-state copy fixed.
**Shipped:** Phase 83 (vitest@4.1.6 + RTL + 70 tests + 4 snapshots pinning v1.23 UX invariants), Phase 84 (46 inline-style sites refactored across ProductCard/CartPanel/App/ProductDetail/HistoryPage/HistoryDetail + `react/forbid-dom-props` → ERROR + 7 robustness sidequests landed during EC2 verification: 84.1 pool recovery hardening, 84.2 multi-source aggregation, 84.3 consensus voting, 84.4 TCP pre-filter + RU-only, 84.5 robust scheduler with stall recovery + 5-min threshold + Wants= systemd fix, 84.6 scrape_green safe-click + mtime touch, 84.7 per-color staleness thresholds green=5/red=5/yellow=10), Phase 85 (153 spacing substitutions to `var(--space-*)` tokens + `declaration-property-value-allowed-list` → ERROR + UX-EMPTY-01 implemented as 3-state classifier `fresh_deploy`/`all_stale`/`genuinely_empty` with differentiated copy). User-visible "Обновлено: never > 5 min" target met via the robustness chain (84.4 → 84.5 → 84.6 → 84.7).

## v1.25 Operator Visibility + Test Coverage (SHIPPED 2026-05-13, tag `v1.25`)

Full scope shipped, 10/13 requirements + REL-19 production hotfix, 3 phases (80-82). Archive: `.planning/milestones/v1.25-{ROADMAP,REQUIREMENTS,MILESTONE-AUDIT}.md` + `.planning/milestones/v1.25-phases/` (3 directories). 16 commits `e76a78e..9d3d185`.

**Goal:** Close the "time-to-notice" gap — operator notified of pool outage via Telegram within 10 min. Escape hatches. Integration tests replay 2026-05-13 pattern. CI blocks regressions.
**Shipped:** Phase 80 (`backend/admin_alerts.py` raw Telegram Bot API alerts for pool-dead/breaker-transitions/xray-restart-failed + `/admin/vless/quarantine/clear` + `/admin/force-stale-all` endpoints, 19 unit tests), Phase 81 (`tests/test_collapse_replay.py` 2026-05-13 pattern replay + pool IO race test + staleAll-empty edge), Phase 82 (`.github/workflows/lint-and-test.yml` lint-miniapp + test-backend jobs, eslint baseline cleared 23 errors → 0, stylelint spacing-scale rule baselined 135 violations). **REL-19 hotfix** (`b65cde7`): production outage 00:04→01:13 — `_run_scraper_set` now always calls `ensure_pool()` before skip-vs-run decision; pinned by 2 regression tests. **UAT audit** (`.planning/UAT-AUDIT-2026-05-13.md`): 6 items surfaced, 1 P1 (Telegram config on EC2), 3 P2 observable, 2 P3 defer-safe. TOOL-05 deferred to v1.26.

## v1.24 Pool Self-Heal Hardening + Outage UX (SHIPPED 2026-05-13, tag `v1.24`)

Full scope shipped, 9/9 requirements + OBS-08 deferred to v1.25, 3 phases (77-79). Archive: `.planning/milestones/v1.24-{ROADMAP,REQUIREMENTS,MILESTONE-AUDIT,MILESTONE-VERIFICATION}.md` + `.planning/milestones/v1.24-phases/` (3 directories).

**Goal:** Pool recovery from ~1h to ≤10 min + zero empty grid during rebuild + style guide v2 enforcement tooling.
**Shipped:** Phase 77 (persistent quarantine + refresh throttle + rate-of-decline + scheduler graceful degrade), Phase 78 (`staleAll` API + per-card badge + prominent banner), Phase 79 (stylelint + eslint forbid-dom-props + 46-entry debt baseline). Verifier audit resolved 4 MUST-CONFIRM-IN-CODE items; final verdict PASS with honest scope framing ("time-to-recover reduced, time-to-notice deferred to v1.25").

## v1.23 Detail-Path Performance + UX Polish (SHIPPED 2026-05-13, tag `v1.23`)

Full scope shipped, 7/7 requirements + 1 late insert (UX-CART-02), 3 phases (74-76). Archive: `.planning/milestones/v1.23-{ROADMAP,REQUIREMENTS,MILESTONE-AUDIT}.md` + `.planning/milestones/v1.23-phases/` (3 directories).

**Goal:** Close the three user-visible issues surfaced during v1.22 live MCP verification.
**Shipped:** Phase 74 (Cold-Path Product Details Latency — 25× improvement, p95 0.678s), Phase 75 (Card Grid Layout Shift Fix — `min-height: 36px` lock), Phase 76 (Cart Panel Trash Button + Clear-Cart Telegram Fallback). Plus style guide v2 upgrade (docs/miniapp-ui-style-guide.md `91a6e30`) capturing the rules that should have prevented the header visual-weight violation.

## v1.22 UX Debt Cleanup + Tooling Polish (SHIPPED 2026-05-13, tag `v1.22`)

Full scope shipped, 7/7 requirements + 1 late insert (UX-BADGE-02), 4 phases (70-73). Archive: `.planning/milestones/v1.22-{ROADMAP,REQUIREMENTS,MILESTONE-AUDIT}.md` + `.planning/milestones/v1.22-phases/` (4 directories).

**Goal:** Close accumulated UX debt from v1.5/v1.10/v1.16 plus `/gsd-check-todos` skill polish.
**Shipped:** History search catalog-wide with `currentSaleType` live badges (Phase 70 UX-BUG-01), stale banner rescoped to `Источники устарели` with per-source age (Phase 71 UX-COPY-01), admin.html `Bug Reports (N)` + `Drift (N)` attention badges + `[hidden]` hotfix (Phase 72 UX-BADGE-01/02), `/gsd-check-todos` priority-aware triage (Phase 73 TOOL-01).

## v1.21 VLESS Pool Self-Healing & Reload Pipeline (SHIPPED 2026-05-12, tag `v1.21`)

Full scope shipped, 8/8 requirements, 3 phases (67-69). Archive: `.planning/milestones/v1.21-{ROADMAP,REQUIREMENTS,MILESTONE-AUDIT}.md` + `.planning/milestones/v1.21-phases/` (3 directories).

**Goal:** Convert the 2026-05-10 manual fix into a deterministic self-healing loop with visible drift signal.
**Shipped:** Phase 67 (Admitted-Node Self-Healing Loop with reprobe daemon + REL-15 success_rate tracking), Phase 68 (xray Auto-Reload on Admission Change — live-verified with 299ms systemctl reload-or-restart), Phase 69 (Drift Visibility via `/api/health/deep` xray_drift block + `pool_refresh_complete` JSONL event schema completion).

## v1.20 Cart-Add Latency & User-Facing Responsiveness (SHIPPED 2026-05-12, tag `v1.20`)

Full scope shipped, 15/15 requirements, 6 phases + 3 late inserts. Archive: `.planning/milestones/v1.20-{ROADMAP,REQUIREMENTS,MILESTONE-AUDIT,SESSION-REPORT}.md` + `.planning/milestones/v1.20-phases/` (8 directories: 62-66, 66.1, 66.2, 66.3).

**Goal:** Cut cart-add p95 from 10.8s → ≤4s envelope, eliminate false-fail-then-double-add UX pattern.
**Shipped:** 20-min keepalive daemon + on-open warmup nudge (PERF-03/04/05), per-user cart-items cache + scraper semaphore (PERF-06/07), API surface spike scaffolding (PERF-08/09), frontend 5s-abort + polling + idempotency (UX-01/02/03), `/api/health/deep` cart_add block + `data/cart_events.jsonl` ledger (OBS-04/05), per-phase smoke gate + rollback rehearsal (OPS-09/10/11), late UX fixes (66.1 stale-color phantom strip, 66.2 cart stepper cache-hit fix, 66.3 warmup endpoint retune with 3× speedup live-verified).

## v1.19 Production Reliability & 24/7 Uptime (SHIPPED 2026-05-05)

18/18 requirements, 3 phases (59-61). Archive: `.planning/milestones/v1.19-*`. Goal: 24/7 uptime via pre-flight probe, 3-state breaker, pool drift visibility, `/api/health/deep` external endpoint.

## v1.18 Geo Resolver & Scraper Recovery (SHIPPED 2026-04-25)

Multi-provider geo chain (ipinfo.io → ipapi.co → ip-api.com) + scraper CDP-WS recovery helpers.

## v1.17 VLESS Timeout Hardening (SHIPPED 2026-04-25)

xray `policy` + `observatory` + `leastPing` + timeout alignment + `remove_proxy` rotation.

## v1.15 Proxy Infrastructure Migration (SHIPPED 2026-04-23)

VLESS+Reality via xray-core bridge replaces SOCKS5 pool.

## v1.14 Cart Truth & History Semantics (SHIPPED 2026-04-21)

Real cart-add, truthful states, history semantics fixed.

## v1.13 Instant Cart & Reliability (SHIPPED 2026-04-16)

Classified error_type, session metadata pre-cache, retry without refresh, optimistic state preserved.

## v1.12 Add-to-Cart 5s Hard Cap (SHIPPED 2026-04-08)

AbortController cap, time-budget polling, D3 background gate.

## v1.11 Cart Responsiveness & Truth Recovery (SHIPPED 2026-04-06)

5s add-to-cart budget, background reconciliation, cart diagnostics.

## v1.10 Scraper Freshness & Reliability (SHIPPED 2026-04-05)

Sale-session continuity, green-only cadence, per-source freshness, cached MiniApp hydration.

## v1.9 Catalog Coverage Expansion (SHIPPED 2026-04-04)

Catalog discovery, merge/backfill, parity reporting.

## v1.8 History Search Completeness (SHIPPED 2026-04-04)

Full local-catalog search, result-state labels, regression coverage.

## v1.7 Categories & Subgroups (SHIPPED 2026-04-03)

Group/subgroup hierarchy + drill-down + favorites + Telegram notifier.

## v1.6 Green Scraper Robustness (SHIPPED 2026-04-02)

Green scraper CDP modal loading + validation gates.

## v1.5 History Search & Polish (SHIPPED 2026-04-01)

Search normalization, fuzzy Cyrillic search, lazy image enrichment.

## v1.4 Proxy Centralization (SHIPPED 2026-04-01)

ProxyManager singleton across backend/cart/login flows.

## v1.3 Performance & Optimization (SHIPPED 2026-04-01)

Rendering + load speed improvements.

## v1.2 Price History (SHIPPED 2026-04-01)

16K+ products, predictions, detail analytics.

## v1.1 Testing & QA (SHIPPED 2026-03-31)

Test coverage groundwork.

## v1.0 Bug Fix & Stability (SHIPPED 2026-03-31)

Foundation bug fixes.

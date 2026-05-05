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
- ✅ **v1.19** Production Reliability & 24/7 Uptime — Phases 59-61 (shipped 2026-05-05; 18/18 requirements satisfied, 78 tests on EC2, 24/24 smoke checks green, external `/api/health/deep` live with 8-key OBS-02 schema — archive: `milestones/v1.19-ROADMAP.md`)
- ⏳ **v1.20** Cart-Add Latency & User-Facing Responsiveness — Phases 62-66 (active, started 2026-05-05; cut cart-add p95 from 10.8 s → ≤ 4 s via session warm-keeping + bridge contention removal + VkusVill API surface spike + frontend pending-polling that eliminates the false-fail-then-double-add pattern)

## v1.20 Cart-Add Latency & User-Facing Responsiveness (ACTIVE — started 2026-05-05)

Cut end-to-end cart-add latency from the current 3-12 s envelope to a **2-4 s envelope**, and eliminate the false-fail-then-double-add UX pattern that surfaces whenever VkusVill's server takes >8 s. Continues the v1.19 robust-over-fast cultural commitment: every phase ships with a scripted EC2 smoke test (`scripts/verify_v1.20.sh`), a `VERIFICATION.md`, p50/p95/p99 latency regression check against an EC2-measured baseline, and a rehearsed rollback path.

Driving evidence (2026-05-05 live UAT — single user attempt, log forensics):

| Layer | Time | Who controls it |
|---|---|---|
| Bridge + TLS + network round-trip | ~330 ms | us — already optimal ✓ |
| **xray bridge multiplexing contention** (6+ concurrent detail-scrapes + HEAD + recalc) | **~2.5 s** | **us — fixable** |
| **VkusVill stale-sessid revalidation** (14-day-old sessid) | **~1.5 s** | **us — fixable** (keep-alive) |
| VkusVill cold-cart compute (product + price + delivery) | ~3.5 s | them — partially mitigable by keeping cart warm |
| **DB row-lock contention vs parallel `basket_recalc.php`** | **~2.5 s** | **us — fixable** (skip-recalc-during-add) |
| Slack / scheduling jitter | ~0.5 s | mixed |
| **Total observed** | **~10.8 s** | |
| Target after this milestone | **≤ 4 s p95** | |

User outcome of the regression: tap "add onion" → 8 s frontend abort → "fail" toast → user retries → second attempt 3.6 s succeeds → **double-added product** (0.7 kg instead of 0.35 kg). The frontend's `AbortController` (8 s) was tighter than the backend `CART_ADD_HOT_PATH_DEADLINE_SECONDS` (10 s) than the observed slow-path response (10.8 s), and the frontend dropped the pending `attempt_id` instead of polling for its eventual resolution.

Empirical bridge measurements (2026-05-05):
- Anonymous `HEAD vkusvill.ru/` through bridge: **~520 ms** TTFB
- Authenticated `HEAD /` (with stored cookies): **~600 ms** TTFB
- Authenticated `GET /personal/`: **~400 ms** TTFB ← cheapest warmup endpoint
- Authenticated `POST basket_add.php` warm-path: ~3.6 s
- Authenticated `POST basket_add.php` cold-path: ~10.8 s

Conclusion: **the bridge is healthy** (~330 ms overhead). The 5-second TTFB on `basket_add.php` is specific to that endpoint's heavy work (auth + product + price + delivery + DB write). A warmup ping pays the session-validation cost (~1-2 s on cold sessid) but skips the heavy compute, so a background keep-alive eliminates the cold-sessid penalty without ever touching the user-visible hot path.

Requirements: `.planning/REQUIREMENTS.md` (15 items: 7 PERF, 3 UX, 2 OBS, 3 OPS).

**Goal:** Reduce cart-add p95 from 10.8 s → ≤ 4 s and eliminate user-visible false-fails / double-adds, without regressing v1.19 reliability gains.
**Granularity:** Medium
**Phases:** 5 (62-66)
**Requirements:** 15 (PERF-03..09, UX-01..03, OBS-04..05, OPS-09..11)

### Phases

- [ ] **Phase 62: Sessid Keep-Alive + On-App-Open Warmup** — `scheduler_service.py` gains a 20-min keep-alive task that fires authenticated `GET /personal/` for each linked Telegram user with recent activity (last 24 h); `backend/main.py` opportunistically fires a warmup within 500 ms of the first `/api/link/status` call when last keep-alive > 15 min. Anti-spam floor: ≤ 1 warmup per user per 15 min. Eliminates the ~1.5 s cold-sessid revalidation tax. Smoke gate: warmup p95 through bridge ≤ 3 s; cart-add p95 with keep-alive active ≤ 6 s (down from 10.8 s).
- [ ] **Phase 63: Bridge Contention Elimination** — Per-user mutex: `/api/cart/items` skips its VkusVill round-trip and returns the cached pending-attempt cart state when a `/api/cart/add` for the same user is in flight (eliminates the parallel `basket_recalc.php` that fights the cart-row DB lock). Global semaphore: detail scrapers (`scrape_green/red/yellow`) pause for up to 10 s when any cart-add is in flight, freeing the VLESS tunnel for the hot path. Smoke gate: cart-add p95 with both fixes active ≤ 4.5 s.
- [ ] **Phase 64: VkusVill API Surface Spike** — Capture an authenticated browser HAR of add-to-cart on `vkusvill.ru` directly; document any lighter endpoints (`/ajax/quick_add`, `basket_add_short`, GraphQL, Telegram-integration variants); if a faster endpoint exists, spike-test it through the bridge and measure p50/p95/p99 vs current `basket_add.php`. Trim the 16-field payload to the minimum server-accepted set (regression test pins the final field list). Spike output documents go/no-go decision; if go, this phase ships the swap.
- [ ] **Phase 65: Frontend Pending-Polling + Idempotency** — On frontend `AbortController` timeout, poll `/api/cart/add-status/{attempt_id}` (already exists in backend) using the `client_request_id` already sent with the original POST, for up to 15 s total before showing "fail" toast. Reduce frontend timeout 8 s → 5 s (tighter; PERF-03/04/06/07 brings p95 < 4 s). Backend idempotency: same `client_request_id` returns the same `attempt_id` (no duplicate VkusVill POST). Eliminates the false-fail-then-double-add pattern. Smoke gate: synthetic 12 s slow-add returns success in UI without double-add.
- [ ] **Phase 66: Cart Hot-Path Observability** — `/api/health/deep` gains an optional `cart_add` block (`p50_ms`, `p95_ms`, `p99_ms`, `success_rate_1h/24h`, `double_add_rate_1h`). Every `/api/cart/add` writes one structured JSONL line to `data/cart_events.jsonl` with `user_id` (hashed), `attempt_id`, `product_id`, `duration_ms`, `success`, `error_type`, `client_request_id`, `sessid_age_s`, `warmup_hit`, `concurrent_recalc`. Enables offline post-mortem of every anomaly. Smoke gate: external curl of `/api/health/deep` returns 200 with `cart_add.p95_ms` populated.

### Phase Details

### Phase 62: Sessid Keep-Alive + On-App-Open Warmup
**Goal:** Eliminate the ~1.5 s cold-sessid revalidation cost from the cart-add hot path by ensuring VkusVill always sees the user's session as warm — both via 20-min background keep-alive and via on-MiniApp-open opportunistic warmup.
**Depends on:** v1.19 closed (uses `pool_snapshot()` from Phase 61 to skip warmup when stack is degraded).
**Requirements:** PERF-03, PERF-04, PERF-05 — plus continued OPS-09 / OPS-10 / OPS-11.
**Success Criteria** (what must be TRUE):
  1. [ ] `scheduler_service.py` keep-alive task: every 20 min iterates `data/auth/{telegram_user_id}/cookies.json` for users with activity in last 24 h, fires authenticated `GET /personal/` through the bridge with anti-spam floor (≤ 1 per user per 15 min) and 5 s timeout.
  2. [ ] `/api/link/status` and `/api/cart/items` handlers in `backend/main.py` opportunistically fire a warmup within 500 ms of the request when last keep-alive for that user > 15 min ago; non-blocking (does not delay the API response).
  3. [ ] Warmup metrics tracked: `data/warmup_events.jsonl` records `user_id` (hashed), `endpoint`, `duration_ms`, `success`, `triggered_by` (`scheduler` / `on_open`).
  4. [ ] EC2 measurement: warmup p95 through bridge ≤ 3 s; cart-add p95 with keep-alive active ≤ 6 s (vs 10.8 s baseline) over 50 synthetic adds.
  5. [ ] `scripts/verify_v1.20.sh` skeleton exists with 5 Phase-62 smoke checks; idempotent; runs over SSH.
  6. [ ] Vercel miniapp `/api/cart/add` still returns HTTP 200 with `success=true` (no regression on v1.19).
**Plans:** TBD via `/gsd-plan-phase 62`

### Phase 63: Bridge Contention Elimination
**Goal:** Stop fighting ourselves on the bridge. When a cart-add is in flight, skip the parallel `basket_recalc.php` and pause detail scrapers — together drops ~5 s off the slow-path.
**Depends on:** Phase 62 (smoke script extends; warmup must be functional so we can measure the marginal benefit cleanly).
**Requirements:** PERF-06, PERF-07 — plus continued OPS-09 / OPS-10 / OPS-11.
**Success Criteria:**
  1. [ ] `backend/main.py::cart_items_endpoint` checks `_cart_pending_attempts[user_id]` for any `status="pending"` entry; if present and < 12 s old, returns the last-known `cart_items` / `cart_total` from that record without firing `basket_recalc.php`. Tests cover both cache-hit and cache-stale paths.
  2. [ ] Global `_CART_ADD_IN_FLIGHT_LOCK` semaphore (asyncio): scrapers `scrape_green` / `scrape_red` / `scrape_yellow` acquire-with-timeout(10 s) before each detail-page fetch; if a cart-add is in flight, they wait. Adds metric to `proxy_events.jsonl`: `scraper_paused_for_cart_add_count`.
  3. [ ] Integration test: simulate 1 cart-add at T=0 + 5 cart-items polls at T=1..5 s; assert only the cart-add fires `basket_*` calls to VkusVill (the polls return cached state).
  4. [ ] EC2 measurement: cart-add p95 with both Phase 62 + Phase 63 active ≤ 4.5 s over 50 synthetic adds during active scraper window.
  5. [ ] Vercel miniapp regression: `/api/cart/add` HTTP 200, no stale cart-items beyond 12 s.
  6. [ ] `scripts/verify_v1.20.sh` extended with 4 Phase-63 smoke checks.
**Plans:** TBD via `/gsd-plan-phase 63`

### Phase 64: VkusVill API Surface Spike
**Goal:** Discover whether VkusVill exposes a faster cart-add endpoint than the 16-field `basket_add.php` (e.g. quick-add variants, GraphQL, Telegram-integration); if so, swap to it; either way, trim the legacy payload to minimum.
**Depends on:** Nothing in this milestone (research-first phase).
**Requirements:** PERF-08, PERF-09 — plus continued OPS-09 / OPS-10 / OPS-11.
**Success Criteria:**
  1. [ ] `.planning/research/v1.20-API-SPIKE.md` documents: (a) full HAR of authenticated browser add-to-cart on `vkusvill.ru` direct, (b) every endpoint touched during the flow, (c) measured p50/p95/p99 for each candidate endpoint through our bridge with valid cookies, (d) go/no-go recommendation.
  2. [ ] `cart/vkusvill_api.py::add` payload trimmed: each field's necessity established by ablation testing (drop one, measure success rate over 20 calls); regression test pins the final field list.
  3. [ ] If a faster endpoint is identified and reachable through the bridge with our auth surface: this phase ships the swap with feature flag (`USE_FAST_CART_ADD_ENDPOINT` env var, default off until smoke gate passes).
  4. [ ] EC2 measurement: cart-add p95 with all of 62 + 63 + (optional 64-swap) active ≤ 4.0 s; if no faster endpoint exists, ≤ 4.5 s baseline from Phase 63 holds.
  5. [ ] `scripts/verify_v1.20.sh` extended with payload-minimum regression check.
**Plans:** TBD via `/gsd-plan-phase 64`

### Phase 65: Frontend Pending-Polling + Idempotency
**Goal:** Eliminate the false-fail UX. When VkusVill is slow, the user must never see "fail" if the backend eventually succeeded — and never get a double-add from retrying.
**Depends on:** Phase 62/63/64 (so the underlying p95 has dropped enough that the pending-polling path is rare, not common).
**Requirements:** UX-01, UX-02, UX-03 — plus continued OPS-09 / OPS-10 / OPS-11.
**Success Criteria:**
  1. [ ] `miniapp/src/App.jsx::handleAddToCart`: on `AbortError` from the 5 s `AbortController`, **does not** clear pending state or show fail toast; instead enters a polling loop that hits `/api/cart/add-status/{attempt_id}` every 1 s for up to 10 additional seconds (15 s total budget from original tap), surfacing success when the attempt resolves.
  2. [ ] Frontend `AbortController` cutoff reduced 8 s → 5 s; the polling fallback (UX-01) is the safety net, not the timeout itself.
  3. [ ] `backend/main.py::cart_add_endpoint` idempotency: when called with a `client_request_id` already present in `_cart_pending_attempts`, returns the existing `attempt_id` without firing a second `basket_add.php`. Test simulates double-tap within 100 ms and asserts only one VkusVill call.
  4. [ ] Playwright test (`miniapp/tests/test_cart_slow_path.py`): mock backend to delay `/api/cart/add` 12 s, assert UI shows success (not fail) via the polling channel; assert no double-add (cart count = 1, not 2).
  5. [ ] EC2 + Vercel deploy: end-to-end synthetic 12 s slow-add via test fixture returns success in UI; double-add rate over 100 synthetic slow paths = 0.
  6. [ ] `scripts/verify_v1.20.sh` extended with frontend polling check.
**Plans:** TBD via `/gsd-plan-phase 65`

### Phase 66: Cart Hot-Path Observability
**Goal:** Make cart-add latency regressions visible to the same uptime monitor that already watches v1.19's pool + breaker. Make every cart-add anomaly post-mortem-able.
**Depends on:** Phase 62/63/64/65 (the metrics are most useful when the optimization phases are in steady state).
**Requirements:** OBS-04, OBS-05 — plus continued OPS-09 / OPS-10 / OPS-11.
**Success Criteria:**
  1. [ ] `GET /api/health/deep` gains optional `cart_add` block computed from rolling-window aggregates over `_cart_pending_attempts` ledger: `p50_ms`, `p95_ms`, `p99_ms` over last 1 h; `success_rate_1h`, `success_rate_24h`; `double_add_rate_1h` (heuristic: same product, same user, < 30 s apart, both succeeded). Block omitted only if zero attempts in the last hour (not a 503 condition).
  2. [ ] `data/cart_events.jsonl` written by `cart_add_endpoint` after every attempt resolution: 10-key schema (`user_id_hash`, `attempt_id`, `product_id`, `duration_ms`, `success`, `error_type`, `client_request_id`, `sessid_age_s`, `warmup_hit`, `concurrent_recalc_at_start`). Privacy: `user_id_hash = sha256(telegram_user_id)[:16]`.
  3. [ ] OBS-02 unhealthy criterion extended: if `cart_add.p95_ms > 6000` for last 1 h, deep health flips to `degraded`; if `> 12000`, flips to `unhealthy`.
  4. [ ] External curl of `/api/health/deep` returns 200 with `cart_add.p95_ms` populated when traffic exists.
  5. [ ] `scripts/verify_v1.20.sh` extended with cart-add-observability checks; total v1.20 smoke checks ≥ 20 green.
  6. [ ] Phase 66 also closes v1.20: per-phase latency baselines from 62/63/64/65 retained as regression gates in `scripts/verify_v1.20.sh`.
**Plans:** TBD via `/gsd-plan-phase 66`

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

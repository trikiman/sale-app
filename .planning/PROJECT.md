# VkusVill Sale Monitor

## What This Is

A family-facing VkusVill discount aggregator that scrapes green/red/yellow price tags, sends Telegram notifications, and lets family members add products to their VkusVill cart without visiting the site. Deployed on AWS EC2 with Vercel frontend proxy at https://vkusvillsale.vercel.app/.

Users only go to VkusVill.ru to finalize delivery and pay.

## Core Value

Family members see every VkusVill discount (green/red/yellow) the moment it appears, and can add items to their cart in one tap — without opening the VkusVill app or website.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- ✓ **SCRAPE-01**: System scrapes green price tags from VkusVill cart page using technical account cookies — existing (scrape_green.py)
- ✓ **SCRAPE-02**: System scrapes red price tags from VkusVill catalog — existing (scrape_red.py)
- ✓ **SCRAPE-03**: System scrapes yellow "купи 6+" multi-buy prices from VkusVill catalog — existing (scrape_yellow.py)
- ✓ **SCRAPE-04**: System runs scrapers sequentially every 3 minutes via scheduler — existing (scheduler_service.py)
- ✓ **SCRAPE-05**: System merges all scraped data into proposals.json with staleness detection — existing (scrape_merge.py)
- ✓ **SCRAPE-06**: System scrapes VkusVill product categories via pure HTTP — existing (scrape_categories.py)
- ✓ **AUTH-01**: User can log in with phone number + SMS code via web app — existing (backend/main.py nodriver)
- ✓ **AUTH-02**: User can set 4-digit PIN for fast re-login without browser — existing
- ✓ **AUTH-03**: User can log out and re-login with PIN using .bak cookies — existing
- ✓ **CART-01**: User can add products to VkusVill cart via API (no browser) — existing (cart/vkusvill_api.py)
- ✓ **CART-02**: User can view cart contents in CartPanel — existing (CartPanel.jsx)
- ✓ **CART-03**: User can remove items and clear cart — existing (basket_update.php integration)
- ✓ **FAV-01**: User can favorite/unfavorite products with instant toggle — existing
- ✓ **FAV-02**: Favorites persist server-side in SQLite — existing
- ✓ **UI-01**: MiniApp displays products in grid/list view with type filters (green/red/yellow) — existing
- ✓ **UI-02**: MiniApp has dark/light theme toggle persisted in localStorage — existing
- ✓ **UI-03**: MiniApp has category filter with horizontal scroll — existing
- ✓ **UI-04**: Product detail drawer shows images, weight, description, nutrition — existing
- ✓ **UI-05**: Cart button shows spinner → checkmark/X feedback (no alert popups) — existing
- ✓ **UI-06**: Auto-refresh via SSE + 60s polling — existing
- ✓ **UI-07**: Stale data warning banner when data is >15 min old — existing
- ✓ **BOT-01**: Telegram bot sends notifications for new green/red prices — existing (bot/notifier.py)
- ✓ **BOT-02**: Telegram bot has /start, /help, /categories, /favorites, /add, /remove, /check commands — existing
- ✓ **BOT-03**: "В корзину" inline button in Telegram adds to cart — existing
- ✓ **DEPLOY-01**: EC2 standalone with 3 systemd services (backend, bot, scheduler) — existing
- ✓ **DEPLOY-02**: Frontend on Vercel with /api/* rewrite to EC2 — existing
- ✓ **DEPLOY-03**: Admin panel with scraper triggers and status monitoring — existing
- ✓ **SEC-01**: Admin endpoints require X-Admin-Token — existing
- ✓ **SEC-02**: Image proxy rejects non-VkusVill domains — existing
- ✓ **SEC-03**: PIN stored as salted hash, not plaintext — existing
- ✓ **SEC-04**: Login rate limiting (4 attempts/10 min) — existing
- ✓ **SEC-05**: Client log rate limiting (30/window) — existing
- ✓ **SEC-06**: Favorites IDOR fix — v1.0
- ✓ **SEC-07**: Cart IDOR fix — v1.0
- ✓ **SEC-08**: Frontend initData auth — v1.0
- ✓ **SCRP-07**: Green scraper ≥90% accuracy (100% achieved) — v1.0
- ✓ **SCRP-08**: No stock=99 placeholder — v1.0
- ✓ **SCRP-09**: Category determinism — v1.0
- ✓ **BOT-04**: All-user notifications — v1.0
- ✓ **BOT-05**: Exact category matching — v1.0
- ✓ **UX-06**: Light theme CSS — v1.0
- ✓ **UX-07**: Composite keys — v1.0
- ✓ **UX-08**: Cart qty=0 filter — v1.0
- ✓ **UX-09**: 403 recovery — v1.0
- ✓ **UX-10**: AnimatePresence delay — v1.0
- ✓ **BACK-01**: Run-All merge sync — v1.0
- ✓ **PROXY-01**: `/api/img` uses ProxyManager rotation instead of SOCKS_PROXY — v1.4
- ✓ **PROXY-02**: Detail gallery images route through backend proxy — v1.4
- ✓ **PROXY-03**: Cart API uses ProxyManager for VkusVill API calls — v1.4
- ✓ **PROXY-04**: Login Chrome uses ProxyManager `--proxy-server` — v1.4
- ✓ **PROXY-05**: ProxyManager is the single gateway for all VkusVill connections — v1.4
- ✓ **SRCH-01**: History search handles non-breaking spaces and Unicode quotes from VkusVill copy-paste — v1.5
- ✓ **SRCH-02**: Fuzzy Cyrillic typo search (single-char substitution fallback) — v1.5
- ✓ **SRCH-03**: Product image population from scraped JSON with lazy enrichment — v1.5
- ✓ **DATA-01..03**: Group/subgroup hierarchy scraped and stored across category DB, merge pipeline, and product catalog — v1.7
- ✓ **UI-08..13**: Main page group/subgroup drill-down and favorites shipped — v1.7
- ✓ **HIST-01..04**: History page group/subgroup filtering and favorites shipped — v1.7
- ✓ **FAV-03..04**: Group/subgroup favorites stored server-side and exposed in UI — v1.7
- ✓ **BOT-06**: Telegram notifier sends alerts for favorited groups/subgroups with dedupe and match reasons — v1.7
- ✓ **HIST-05..07**: History search returns full local-catalog matches across live-sale, history-only, and catalog-only states without hidden scope restrictions — v1.8
- ✓ **UI-14..15**: History search clearly labels live, history-only, and catalog-only result states — v1.8
- ✓ **QA-01**: Automated regression coverage protects mixed History search results — v1.8
- ✓ **HIST-08**: Continuous sale sessions survive transient scrape misses and only close after confirmed 60-minute healthy absence — v1.10
- ✓ **BOT-07**: New-item alerts require confirmed sale exit/reentry instead of first-ever-seen IDs — v1.10
- ✓ **SCRP-10..12**: Scheduler supports green-only freshness passes, exposes per-source freshness, and keeps last valid snapshots when colors are stale — v1.10
- ✓ **OPS-02..03**: Cycle-state diagnostics and stale/failure visibility now surface through admin payloads, logs, and MiniApp warnings — v1.10
- ✓ **UI-16..18**: Main screen hydrates from cached data, card enrichment is lower-pressure, and no private API switch was taken without evidence — v1.10
- ✓ **QA-03**: Milestone regression suite covers continuity, scheduler freshness, notifier behavior, and the current backend API contract — v1.10
- ✓ **CART-04..09**: Hard 5.0-second add-to-cart UX budget on the click path, with neutral pending state and background reconciliation — v1.11
- ✓ **UI-19**: User sees non-blocking "checking cart" message when truth recovery takes longer than 5 seconds — v1.11
- ✓ **OPS-04, QA-04**: Cart diagnostics surfaced in admin payloads, and bounded add contract protected by targeted regression tests — v1.11
- ✓ **CART-10..14**: AbortController hard cap (tuned 5s→8s in v1.13), time-budget polling, 404 immediate stop, D3 background-handoff gate — v1.12
- ✓ **CART-15..16**: Cart-add endpoint returns typed `error_type` and logs root cause with diagnostic context — v1.13
- ✓ **PERF-01..02**: Login persists `sessid`/`user_id`/`sessid_ts`; stale sessid auto-refreshes before it can cause a cart failure — v1.13
- ✓ **ERR-01..02**: Distinct error messages per failure mode; retry-without-refresh capability — v1.13
- ✓ **CART-17..18**: Quantity stepper appears immediately after success; `refreshCartState` preserves optimistic rows on `source_unavailable` — v1.13
- ✓ **CART-19**: MiniApp add-to-cart places the selected product into the user's real VkusVill cart — live verified, POST /api/cart/add 200 for product 33215 — v1.14
- ✓ **CART-20**: Cart UI only transitions to success/quantity-control state when backend truth confirms the add — v1.14
- ✓ **CART-21**: Ambiguous/failed adds land in a truthful stable state with retry/recovery path — v1.14
- ✓ **HIST-09**: Stale scrape gaps and merge artifacts no longer create fake restocks or fake reentries — v1.14
- ✓ **HIST-10**: History/notifier semantics distinguish continued sale, first appearance, and true return-to-sale — v1.14
- ✓ **HIST-11**: Persisted history/session data was repaired — product 100069 sessions 56→5, `short_gaps_remaining = 0` — v1.14
- ✓ **OPS-05**: Admin/status and logs now explain why a cart attempt or sale-session transition received its classification — v1.14
- ✓ **QA-05**: Milestone verification includes live production cart-add proof and history-semantic checks — v1.14

- ✓ **REL-01..12, OBS-01..03, OPS-06..08**: v1.19 Production Reliability & 24/7 Uptime — 18/18 requirements satisfied, 78 tests on EC2, 24/24 smoke green, external `/api/health/deep` live with 8-key OBS-02 schema — v1.19 (shipped 2026-05-05)
- ✓ **PERF-03..05**: v1.20 Sessid keep-alive + on-app-open warmup + anti-spam floor (Phase 62 + late 66.3 endpoint retune /personal/ → basket_recalc, 3× speedup live-verified) — v1.20 (shipped 2026-05-12)
- ✓ **PERF-06..07**: v1.20 Per-user cart-items 12s cache during pending cart-add + global scraper semaphore with 10s timeout (Phase 63) — v1.20
- ✓ **PERF-08..09**: v1.20 USE_FAST_CART_ADD_ENDPOINT feature-flag scaffolding + ablation harness (Phase 64 scaffolding; HAR spike deferred) — v1.20
- ✓ **UX-01..03**: v1.20 Frontend 5s AbortController + polling on AbortError + client_request_id idempotency (Phase 65 + late 66.2 stepper cache-hit fix) — v1.20
- ✓ **OBS-04..05**: v1.20 `/api/health/deep` cart_add block + `data/cart_events.jsonl` 11-key ledger (Phase 66) — v1.20
- ✓ **OPS-09..11**: v1.20 scripts/verify_v1.20.sh with 19 smoke checks + v1.19 cross-version regression gate + rollback rehearsed per phase — v1.20
- ✓ **66.1 Stale-Color Phantom Strip (late insert)**: `/api/products` drops products of stale color; matches VkusVill "Зелёных ценников сейчас нет" empty-state UX — v1.20
- ✓ **REL-13..15**: v1.21 VLESS Pool Self-Healing & Reload Pipeline — admitted-node reprobe daemon every 10 min, xray auto-reload on admission diff via passwordless systemctl (live-verified 299ms reload), per-node success_rate tracking with dead-host exclusion — v1.21 (shipped 2026-05-12)
- ✓ **OBS-06..07**: v1.21 /api/health/deep xray_drift block (degraded >5min, unhealthy + stale cycle >10min) + pool_refresh_complete JSONL event with admission diff + success_rate_drops — v1.21
- ✓ **OPS-12..14**: v1.21 scripts/verify_v1.21.sh with 13 smoke checks live-verified on EC2 + v1.20/v1.19 cross-version regression + per-phase rollback rehearsal — v1.21
- ✓ **UX-BUG-01**: v1.22 History search returns ALL products from `product_catalog` matching the query; live-sale rows carry `currentSaleType` for inline green/red/yellow badges on ghost cards (Phase 70) — v1.22 (shipped 2026-05-13)
- ✓ **UX-COPY-01**: v1.22 Stale banner rescoped to `Источники устарели` with per-source age; semantically distinct from the updated-time header (Phase 71) — v1.22
- ✓ **UX-BADGE-01/02**: v1.22 `backend/admin.html` renders `Bug Reports (N)` + `Drift (N)` attention badges + `[hidden]` CSS hotfix (`825008c`) after live MCP caught `.badge { display: inline-block }` override (Phase 72) — v1.22
- ✓ **TOOL-01**: v1.22 `/gsd-check-todos` skill adds `priority: P1|P2|P3|P4` frontmatter + P1-first sort + visible priority labels (Phase 73) — v1.22
- ✓ **OPS-15..17**: v1.22 `scripts/verify_v1.22.sh` chains v1.21→v1.20→v1.19 smoke scripts; 9/9 live-verified on EC2 + per-phase rollback rehearsal — v1.22

### Active

<!-- Current scope. Building toward these. -->

- v1.23 Detail-Path Performance + UX Polish. Scope: close the three user-visible issues surfaced during v1.22 live MCP verification — cold-path `/api/product/{id}/details` taking 8-15s on first open (legacy pre-v1.15 SOCKS5-era HEAD probe loop, now redundant since xray leastPing picks fastest outbound), card grid reflow when cart button morphs into quantity stepper, cart panel missing a trash button per row. 3 phases (74-76), 7 requirements (2 PERF, 2 UX, 3 OPS), all small.

## Current Milestone: v1.23 Detail-Path Performance + UX Polish

**Goal:** Cold-path card open p95 ≤ 2s. Zero card-grid layout shift. Trash button on every cart-panel row.

**Target features** (finalized via `.planning/REQUIREMENTS.md` v1.23):
- Cold-path `GET /api/product/{id}/details` p95 ≤ 2s. Remove per-proxy HEAD probe loop in `backend/main.py::product_details` (pre-v1.15 SOCKS5-era artifact; xray `observatory`+`leastPing` already picks fastest live outbound per v1.17). Tighten httpx timeouts: connect 4s→1s, read 6s→3s. Keep 3 retries. (PERF-10, Phase 74)
- `data/detail_events.jsonl` ledger with one line per `/api/product/{id}/details` call: `{ts, product_id, duration_ms, cached, retry_count, outcome}`. Bounded file, tail-readable from admin. Follows v1.20 `cart_events.jsonl` pattern. (PERF-11, Phase 74)
- Product card grid reserves the stepper slot via fixed min-height so the "not-in-cart" (cart button) and "in-cart" (full stepper) states occupy the same vertical space. Neighbors no longer reflow. Lighthouse CLS ≤ 0.1. (UX-SHIFT-01, Phase 75)
- Cart panel item rows gain a trash/remove button firing `POST /api/cart/remove` (backend already exists — frontend wiring only). Optimistic UI with spinner, error toast + re-enable on failure, panel refresh on success. (UX-CART-01, Phase 76)
- `scripts/verify_v1.23.sh` grows phase-by-phase and chains `verify_v1.22.sh all` (which chains v1.21→v1.20→v1.19) so all five milestones' smoke gates stay green through v1.23 deploy (OPS-18/19/20).

**Key context:**
- All 3 issues captured as todos 2026-05-13 during v1.22 live MCP session. Confirmed via live Chrome DevTools MCP on https://vkusvillsale.vercel.app/: first card open ~16s, second open ~2s (cache hit); card grid visibly reflows when stepper appears.
- Cold-path root cause is a legacy pre-v1.15 SOCKS5 pool-era per-proxy HEAD probe loop. Since v1.17 (xray observatory+leastPing) the bridge at `127.0.0.1:10808` always points at the fastest live outbound; since v1.19 pre-flight probes already catch broken bridges; since v1.21 the reprobe daemon + REL-15 success_rate tracking keep the admitted pool alive. The Python-side probe is dead weight at 4-12s cost.
- Phase 74 is backend-only (python). Phases 75/76 are frontend-only (React/CSS). Scope tight like v1.21/v1.22 — no creep.
- User preference (reaffirmed 2026-05-13 during v1.22 verification): "one ping is 30-40ms, why 4 sec I don't get" — 4s timeout is absurd for a healthy VLESS bridge. 1s connect / 3s read is still 10-30x over the healthy case with 2-3x margin on worst case.
- Every phase requires live MCP verification before declaring shipped — the v1.21 "push ≠ verified" lesson + the v1.22 Phase 72 `[hidden]` hotfix both proved code review alone is insufficient for UI changes. UI bugs surface only in real browsers.
- User preference: robust-over-fast, atomic commits per plan deliverable, STOP before `/gsd-complete-milestone` for manual review.

## Previous Shipped Milestone: v1.22 UX Debt Cleanup + Tooling Polish (2026-05-13)

**Goal:** Clear accumulated UX debt from earlier milestones (v1.5/v1.10/v1.16) that never closed the UI side, plus a skill-file polish for `/gsd-check-todos` priority-aware triage.

**Shipped features:**
- Phase 70 UX-BUG-01 History search catalog-wide: `backend/main.py::history_search` now returns ALL products from `product_catalog` matching the query (not just `total_sale_count > 0` rows). Live-sale matches carry `currentSaleType` for green/red/yellow badge rendering. Regression guarded by `backend/test_history_search_catalog_wide.py` (force-added since `test_*.py` is gitignored).
- Phase 71 UX-COPY-01 Stale banner clarification: rescoped to `Источники устарели` (plural, per-source) with inline age annotation. User no longer sees the contradictory "Обновлено: 09:36 + stale warning" pair.
- Phase 72 UX-BADGE-01/02 admin.html attention badges: `Bug Reports (N)` + `Drift (N)` badges in status row, mirroring existing `proxy-badge`/`cart-pending-count` patterns. UX-BADGE-02 folded in as late insert for the v1.21 `xray_drift` card. Live MCP caught a `.badge { display: inline-block }` rule overriding `[hidden]` — shipped hotfix `825008c` adding `[hidden] { display: none !important; }`.
- Phase 73 TOOL-01 `/gsd-check-todos` skill polish: `priority: P1|P2|P3|P4` frontmatter across all pending todos, P1-first sort in the CLI output, visible priority labels. Kiro-side only, local 3/3 smoke green + CLI synthetic-fixture validation.
- `scripts/verify_v1.22.sh` 9 smoke checks + chains v1.21→v1.20→v1.19 regression. 7/7 requirements + 1 late insert (UX-BADGE-02), 16 commits `5513ede..f56f285` (including `[hidden]` hotfix `825008c` and obsolete todo cleanup `f56f285`).

_Archive: `.planning/milestones/v1.22-{ROADMAP,REQUIREMENTS,MILESTONE-AUDIT}.md`, `.planning/milestones/v1.22-phases/{70,71,72,73}-*/`. Tag: v1.22._

## Previous Shipped Milestone: v1.21 VLESS Pool Self-Healing & Reload Pipeline (2026-05-12)

**Goal:** Convert the 2026-05-10 manual fix (`sudo systemctl restart saleapp-xray` after pool whitelist rebuild) into a deterministic self-healing loop with visible drift signal, so the next outage is caught in minutes not days.

**Shipped features:**
- Phase 67 admitted-node reprobe daemon firing every 10 min through the running bridge (REL-13), with REL-15 per-host success_rate tracking (100-sample sliding window, dead at rate<0.1 with ≥20 samples). Live-verified 18/18 admitted nodes passing reprobe post-hotfix.
- Phase 68 xray auto-reload on admission set diff via `sudo systemctl reload-or-restart saleapp-xray` (throttled 90s, 30s timeout). Passwordless sudoers deployed to `/etc/sudoers.d/saleapp-xray-reload`. First live reload executed 2026-05-12 in **299ms**. Systemd stays lifecycle owner per v1.15 D7.
- Phase 69 `/api/health/deep` `xray_drift` block (admitted_hosts, active_outbounds, drift_count, drifted_hosts, first_seen_at) with 5-min degraded / 10-min unhealthy thresholds. Live drift injection proved detection+recovery. `pool_refresh_complete` JSONL event carries full admission diff + success_rate_drops.
- `scripts/verify_v1.21.sh` 13 smoke checks, 13/13 green live on EC2 post-deploy. Chains `verify_v1.20.sh` + `verify_v1.19.sh`.

_Archive: `.planning/milestones/v1.21-{ROADMAP,REQUIREMENTS,MILESTONE-AUDIT}.md`, `.planning/milestones/v1.21-phases/{67,68,69}-*/`. Tag: v1.21._

## Previous Shipped Milestone: v1.20 Cart-Add Latency & User-Facing Responsiveness (2026-05-12)

**Goal:** Cut end-to-end cart-add latency from the 3-12 s envelope to 2-4 s, and eliminate the false-fail-then-double-add UX pattern observed 2026-05-05 live UAT.

**Shipped features:**
- 20-min sessid keep-alive daemon + on-MiniApp-open warmup nudge with anti-spam floor
- Per-user cart-items 12s cache + global scraper semaphore freeing the VLESS tunnel during cart-add
- USE_FAST_CART_ADD_ENDPOINT feature-flag scaffolding (HAR spike deferred as tech debt)
- Frontend 5s AbortController + on-AbortError polling + backend client_request_id idempotency (eliminates the double-add UX bug)
- /api/health/deep cart_add block (p50/p95/p99, success_rate, double_add_rate) + data/cart_events.jsonl 11-key ledger
- Late fixes: 66.1 stale-color phantom strip (phantom cards when source stale), 66.2 cart stepper cache-hit UI fix (⟲ flash after add), 66.3 warmup endpoint retune `/personal/` → `basket_recalc` (3× speedup live-verified 6s → 1.8s)
- scripts/verify_v1.20.sh with 19 smoke checks + v1.19 cross-version regression gate + rollback rehearsed per phase

_Archive: `.planning/milestones/v1.20-{ROADMAP,REQUIREMENTS,MILESTONE-AUDIT}.md`, `.planning/milestones/v1.20-phases/`, `.planning/milestones/v1.20-SESSION-REPORT-2026-05-12.md`. Tag: v1.20._

## Previous Shipped Milestone: v1.19 Production Reliability & 24/7 Uptime (2026-05-05)

**Goal:** Keep the VkusVill sale app continuously healthy 24/7 by hardening the EC2 data pipeline against post-v1.18 failure modes (pool 25→13, 162 consecutive scraper failures, 30/30 detail-proxy timeouts).

**Shipped features:**
- Corrected pre-flight VLESS bridge probe (12 s timeout, cap 2 rotations, balancer-preferred fallback)
- xray `observatory.probeURL` aligned with VkusVill (not Google) so `leastPing` ranks by real-target reachability
- Graduated 3-state circuit breaker (closed/open/half_open) with exponential backoff capped at 30 min, persisted state
- Unauthenticated `GET /api/health/deep` returning 200/503 + `reasons[]` for external uptime monitors, 8-key OBS-02 schema
- Pool snapshot accessor + enriched `proxy_events.jsonl` (multi-day drift now visible in real time)
- 78 tests on EC2, 24/24 smoke green, full per-phase rollback rehearsal

_Archive: `.planning/milestones/v1.19-{ROADMAP,REQUIREMENTS,MILESTONE-AUDIT}.md`._

## Previous Shipped Milestone: v1.14 Cart Truth & History Semantics (2026-04-21, closed 2026-04-22)

**Goal:** Make add-to-cart work in real user flows and make history/restock semantics reflect real sale transitions instead of fake reentries.

**Shipped features:**
- Real add-to-cart success from MiniApp to the user's VkusVill cart (live verified on production)
- Truthful cart UI states and recovery when upstream add/refresh is ambiguous
- History/session logic that no longer invents fake restocks or fake "new again" events
- Persisted history/session data repaired — thousands of fake short-gap session splits removed
- Live verification captured real cart add/remove cycle + stale-session simulation + post-repair history counts

## Previous Shipped Milestone: v1.13 Instant Cart & Reliability (2026-04-16, closed 2026-04-22)

**Goal:** Make add-to-cart feel instant and fix the failures that made cart adds silently drop on the user-facing path.

**Shipped features:**
- Classified `error_type` contract on `/api/cart/add` with diagnostic logging
- Sessid/user_id/sessid_ts pre-cached at login so the first cart add skips warmup GET
- Stale sessid (>30 min) auto-refresh path
- Distinct user-visible error messages per failure mode, with retry-without-refresh
- Quantity stepper + optimistic state preservation on `source_unavailable`

_v1.13 was initially audit-blocked (missing `50-VERIFICATION.md`, pending live UAT). Both gaps were closed retroactively on 2026-04-22 using v1.14 phase 55 live evidence._

## Previous Shipped Milestone: v1.11 Cart Responsiveness & Truth Recovery

**Goal:** Make add-to-cart feel fast and trustworthy by capping the click-path wait at 5 seconds, moving ambiguous recovery off the main interaction path, and tightening cart diagnostics.

**Target features:**
- Hard 5.0-second add-to-cart UX budget on the click path
- Background cart reconciliation after ambiguous add timeouts instead of inline wait chaining
- Backend cart/session recovery tuned for fast acknowledgement plus later truth recovery
- Diagnostics and regression coverage for slow-add latency, late success, and duplicate-tap edge cases

## Previous Shipped Milestone: v1.10 Scraper Freshness & Reliability

**Goal:** Keep sale/newness signals correct and the main sale screen responsive by making scrape cadence, failure handling, and card loading more resilient.

**Target features:**
- Continuous-sale guardrails so transient scrape misses do not create fake re-appearances, new sessions, or duplicate notifications
- Scheduler rebalance so green refreshes happen more often than red/yellow without breaking the current sequential scraper model
- Failure/staleness alerting that makes bad cycles visible before they silently poison history, notifier, or UI freshness
- Main-screen and card-path performance work, including profiling any API/card enrichment bottlenecks before changing the data path

## Previous Shipped Milestone: v1.9 Catalog Coverage Expansion (2026-04-04)

Shipped across phases 36-38:
- Supplemental catalog discovery now covers stable source-based offline discovery beyond the hardcoded category crawl
- Catalog merge/backfill now persists newly discovered products into local catalog artifacts without clobbering richer metadata
- Repeatable parity reports and regression coverage now make local-catalog completeness visible and testable

## Shipped: v1.7 Categories & Subgroups (2026-04-03)

Group/subgroup hierarchy shipped across scraper data, main/history filters, favorites, and Telegram notifications.

## Shipped: v1.6 Green Scraper Robustness (2026-04-02)

Green scraper reliability improvements — CDP Network interception, modal load completion, count validation gate.

## Shipped: v1.5 History Search & Polish (2026-04-01)

Search and polish improvements for the History page:
- Exact name search with non-breaking space and quote normalization
- Fuzzy Cyrillic typo search with character substitution fallback (е↔а, а↔о, и↔ы, ё↔е)
- Lazy image enrichment from scraped JSON files with 5-min cache and DB persistence
- Image coverage improved from 3.4% to ~70-80%

### Out of Scope

- Docker containerization — not needed, systemd works fine
- HTTPS/domain setup — Vercel handles HTTPS already
- Proxy pool scaling — handle separately if needed (8 IPs sufficient for 5-user family app)
- Mobile app — web-first, Telegram MiniApp is the mobile experience
- Cookie encryption at rest — low risk for family-only app
- OAuth login — VkusVill only supports phone+SMS

## Next Milestone Candidates

- **v1.24 Observability & Tooling Deep Dive**: Telegram alerts on `xray_restart_failed` and breaker state transitions (v1.19 REL-FUT-05); historical drift trace / rate-of-change panels; Vitest/RTL wiring for miniapp (caught only via live MCP in v1.22; snapshot test would've caught the `[hidden]` CSS bug in CI); multi-select fold-into-milestone in `/gsd-check-todos`; `/gsd-add-todo` skill priority capture at creation time (P4 pending todo).
- **v1.25 Detail-Path Deep Dive** (conditional on v1.23 PERF-10 results): Phase 64 HAR capture + ablation sweep + `FAST_CART_ADD_URL` go/no-go decision (v1.20 deferred); Playwright slow-path test for miniapp (v1.20 NEEDS_OPERATOR-1); background pre-warm of top-visible product details (v1.23 out-of-scope — "measure PERF-10 alone first"); SSE `/api/stream` graceful-shutdown short-circuit on SIGTERM (observed stuck restart loops during v1.22 Phase 72 verification).
- Reverse-engineered/private API path for green data only if cadence + robustness work still cannot meet freshness targets
- Larger-scale frontend data-path work such as server-driven pagination or virtualization if card performance still degrades as product volume grows

## Context

### Architecture (3 Services)

```
┌──────────────────────────────────────────────────────────┐
│  Telegram Bot  │  Scheduler        │  Backend (FastAPI)  │
│  python main.py│  scheduler_svc.py │  uvicorn backend    │
├──────────────────────────────────────────────────────────┤
│  Notifications │  Scrape prices    │  Admin panel        │
│  "В корзину"   │  every 3 min      │  Web app (products) │
│  "Открыть"     │  tech account     │  Cart API           │
│  /login        │                   │  Login API          │
└──────────────────────────────────────────────────────────┘
```

### Tech Stack
- **Bot**: `python-telegram-bot`
- **Database**: SQLite (`salebot.db`) via SQLAlchemy
- **Price Scrapers**: `nodriver` (CDP-native) + async JS evaluation
- **Category Scraper**: `aiohttp` + `BeautifulSoup` (pure HTTP, MAX_CONCURRENT=3)
- **Cart API**: `cart/vkusvill_api.py` (raw Cookie header, `httpx`)
- **Login**: `nodriver` (CDP-native) for web app login
- **Backend**: FastAPI
- **Frontend**: React (Vite, built → served by backend)
- **Hosting**: AWS EC2 (t3.micro) + Vercel (frontend proxy)

### Two Account Types
| | Technical Account | User Accounts |
|---|---|---|
| **Purpose** | Scrape prices | Add to user's cart |
| **Cookies** | `data/cookies.json` | `data/auth/{phone}/cookies.json` |
| **Used by** | Scheduler only | Telegram + Web app |

### Known Technical Constraints
- VkusVill bans concurrent connections (not rate), keep MAX_CONCURRENT ≤ 3
- VkusVill masked inputs require CDP `Input.dispatchKeyEvent` (JS setters don't work)
- `--headless=new` crashes Chrome on Win11, use offscreen window
- nodriver swallows JS errors as ExceptionDetails dicts — always use `safe_evaluate()`
- Green pricing depends on Chrome profile state beyond just cookies
- All scrapers must run sequentially (Chrome port/profile conflicts)

### Deployment
- **EC2**: `13.60.174.46:8000`, 3 systemd services, Xvfb for headless Chrome
- **Vercel**: `vkusvillsale.vercel.app`, rewrites /api/* to EC2
- **Last verified**: 2026-04-21, scheduler recovery + fresh product payload confirmed on EC2/Vercel

## Constraints

- **Tech stack**: Python + React + nodriver — established, don't change
- **Platform**: VkusVill's anti-bot measures require CDP-native browser automation
- **Users**: Family only (up to 5 accounts + 1 technical)
- **Server**: t3.micro (1GB RAM) — Chrome uses ~233MB, must be careful with resources
- **SMS limits**: VkusVill allows max 4 SMS per day per phone — minimize live auth testing

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| nodriver over Playwright/undetected_chromedriver | CDP-native bypasses anti-bot, Playwright gets address-binding issues | ✓ Good |
| Raw Cookie header for cart API | requests cookie jar can't handle __Host-PHPSESSID | ✓ Good |
| Sequential scrapers (not parallel) | Chrome instances conflict on ports/profiles | ✓ Good |
| Session cookies in plain JSON files | Family-only app, low risk | ⚠️ Revisit if user base grows |
| Vercel + EC2 split | Free HTTPS/CDN via Vercel, compute on EC2 | ✓ Good |
| ProxyManager singleton for all VkusVill traffic | Centralized proxy rotation, dead proxy auto-removal, shared pool | ✓ Good |
| Smart CDN routing (cdn→direct, img→proxy) | CDN images work direct from EC2, non-CDN are geo-blocked | ✓ Good |
| Lazy image enrichment from scraped JSON | Avoids scraping 16K product pages; images auto-populate as products appear on sale | ✓ Good |
| Fuzzy search only on empty results | Zero perf impact for correct queries; ~300ms for typo fallback | ✓ Good |
| Exact category favorite keys (`group:X`, `subgroup:X/Y`) | Shared contract across main page, history page, and notifier | ✓ Good |
| History chip scope follows history dataset | Prevent empty subgroup chips when the history list only shows products with sale history | ✓ Good |
| Notifier falls back to `product_catalog` metadata | `proposals.json` sale snapshot does not always carry group/subgroup fields yet | ✓ Good |
| Expand local `product_catalog` before adding hybrid search | Keeps History search local-first and moves live VkusVill dependency into offline ingest instead of user queries | — Active |
| Per-cycle health snapshot before merge/history updates | Missing one scrape cycle should not split continuous sale sessions or create fake restocks | ✓ Good |
| Full-cycle + green-only dual cadence | Green needs fresher refreshes, but red/yellow must still keep a predictable full-cycle target | ✓ Good |
| Last-good snapshot hydration in MiniApp | Cached content is safer than a long blocking spinner when freshness warnings remain visible | ✓ Good |
| Metadata-first cart session bootstrap | Persist `sessid` and `user_id` with saved cookies so cart add can skip warmup GETs when metadata is already known | ✓ Good |
| Opt-in pending cart add contract | Keep legacy timeout behavior for current callers, but let new clients switch to `202 pending` plus attempt polling without blocking the hot path | — Active |
| Pending cart UI is neutral, not failure-first | Ambiguous add results should show "checking cart" and keep the app usable instead of turning red before truth is known | ✓ Good |
| In-cart products use synced quantity controls | Cards and detail drawer should switch into the same typed `шт/кг` quantity control instead of reverting to a plain add button | ✓ Good |
| Cart diagnostics belong in admin/status + logs | Operators should inspect cart attempt timing and reconciliation through existing admin surfaces rather than adding new end-user diagnostics UI | ✓ Good |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-13 after v1.22 (UX Debt Cleanup + Tooling Polish) shipped, tagged, and live-verified on EC2 (7/7 requirements + 1 late insert UX-BADGE-02, 4 phases 70-73, 16 commits including `[hidden]` hotfix `825008c` and obsolete todo cleanup `f56f285`). v1.23 (Detail-Path Performance + UX Polish) initiated to close 3 issues surfaced during v1.22 live MCP verification: cold-path card open 8-15s, card grid reflow on stepper morph, cart panel missing trash button. 3 phases (74-76), 7 requirements (2 PERF, 2 UX, 3 OPS), scope tight per v1.21/v1.22 discipline.*


# Milestones

## v1.3 Roadmap: VkusVill Sale Monitor (Backfilled: 2026-05-03)

**Note:** Synthesized from archive snapshot by `/gsd-health --backfill`. Original completion date unknown.

---

## v1.14 Cart Truth & History Semantics (Shipped: 2026-04-21, closed: 2026-04-22)

**Phases completed:** 4 phases (52-55), 4 plans

**Audit status:** passed (see `.planning/milestones/v1.14-MILESTONE-AUDIT.md`)

**Key accomplishments:**

- MiniApp add-to-cart now actually lands the selected product in the user's real VkusVill cart, live-verified on production with `POST /api/cart/add` returning 200 for product 33215 on a real guest session and updated basket totals
- `/api/cart/items` now returns real basket lines instead of `source_unavailable` fallback, so the cart UI no longer needs to compensate for a lying backend
- Stale-session cart add now completes in ~2.7 s without hitting the old 10 s refresh stall, making the fast path fast for every user not just warm ones
- Sale history no longer invents fake restocks or fake reentries from stale scrape gaps, merge artifacts, or sub-60-minute gap continuity heuristics
- Already-persisted fake session splits were repaired in production — yellow product 100069 collapsed from 56 sessions back to 5, and the production gap query now reports `short_gaps_remaining = 0`
- Milestone closure was gated on fresh live evidence (QA-05) rather than code-path review alone, so "we verified it" means a real production transaction

---

## v1.13 Instant Cart & Reliability (Shipped: 2026-04-16, closed: 2026-04-22)

**Phases completed:** 5 phases (47-51), 7 plans

**Audit status:** passed (retroactive closure 2026-04-22 — supersedes the 2026-04-21 `gaps_found` audit — see `.planning/milestones/v1.13-MILESTONE-AUDIT.md`)

**Key accomplishments:**

- The cart-add endpoint now returns a typed `error_type` field (`auth_expired`, `product_gone`, `transient`, `timeout`, `api`, `unknown`) so the frontend can route distinct user-visible states instead of showing a generic 500
- Every cart failure path in the backend now logs the specific root cause with proxy/session/upstream context so operators can attribute why a given attempt was classified the way it was
- Login now persists `sessid` + `user_id` + `sessid_ts` into `cookies.json` so the first cart add no longer blocks on a warmup GET
- Stale sessid (>30 min) now auto-refreshes via a bounded warmup GET before it can cause a cart failure, with the refreshed timestamp written back to disk
- Users now see distinct messages for sold-out, session-expired, VkusVill-down, and network-error states, and transient errors leave the button in a retry state
- The quantity stepper now appears immediately after a successful cart add, and `refreshCartState` no longer overwrites optimistic rows when the backend returns `source_unavailable`
- Live verification was completed via v1.14 phase 55 (real production cart add for product 33215 returned `200`, stale `sessid_ts=1` add completed in ~2715 ms without the old refresh stall)

---

## v1.12 Add-to-Cart 5s Hard Cap (Shipped: 2026-04-08)

**Phases completed:** 1 phase (46), 1 plan, 2 tasks

**Audit status:** passed (superseded by v1.13 tuning — see `.planning/milestones/v1.12-MILESTONE-AUDIT.md`)

**Key accomplishments:**

- The add-to-cart fetch now uses an AbortController with a hard cap on the visible wait so no request can silently outlive the budget
- The pending-attempt poll loop now uses a remaining-time budget instead of a fixed iteration count, with a per-poll AbortController capped to the remaining budget
- The poll loop exits immediately on a 404 status so missing attempts can no longer keep users waiting
- A "Добавляем в фоне" background-handoff message now fires before polling when the initial fetch already consumed most of the budget
- The original 5-second cap was tuned to 8 seconds by v1.13 after live testing showed 5 s was too tight on real VkusVill latency; the architectural contract and all diagnostic logs carry over

---

## v1.11 Cart Responsiveness & Truth Recovery (Shipped: 2026-04-06)

**Phases completed:** 3 phases, 9 plans, 0 tasks

**Key accomplishments:**

- The cart hot path now reuses saved session metadata and returns an ambiguous timeout result instead of doing an inline cart read before responding
- The backend now has an opt-in pending add contract with short-lived dedupe and a status route for later reconciliation
- The pending cart contract is now protected by focused backend tests for legacy timeout compatibility, dedupe reuse, and status-route reconciliation
- The add-to-cart click path now uses the pending backend contract so the UI stops blocking on inline cart refresh loops and shows a neutral checking state instead
- The cart contract now preserves decimal quantities and exposes a set-quantity route, so real `шт/кг` controls no longer depend on fake frontend-only state
- Confirmed in-cart products now switch into a synced VkusVill-like quantity control across cards and detail views, with typed `шт` and `кг` entry
- Recent cart attempt lifecycle data is now exposed through `/admin/status`, rendered in the admin dashboard, and logged with explicit attempt IDs
- The cart regression suite now covers immediate success, pending transitions, quantity routes, and the admin diagnostics payload in one repeatable command
- The repo now has a current lightweight cart UI sanity helper and a verification artifact that records both automated cart diagnostics checks and browser/manual limitations

---

## v1.11 Cart Responsiveness & Truth Recovery (Shipped: 2026-04-06)

**Phases completed:** 3 phases, 9 plans, 0 tasks

**Key accomplishments:**

- The cart hot path now reuses saved session metadata and returns an ambiguous timeout result instead of doing an inline cart read before responding
- The backend now has an opt-in pending add contract with short-lived dedupe and a status route for later reconciliation
- The pending cart contract is now protected by focused backend tests for legacy timeout compatibility, dedupe reuse, and status-route reconciliation
- The add-to-cart click path now uses the pending backend contract so the UI stops blocking on inline cart refresh loops and shows a neutral checking state instead
- The cart contract now preserves decimal quantities and exposes a set-quantity route, so real `шт/кг` controls no longer depend on fake frontend-only state
- Confirmed in-cart products now switch into a synced VkusVill-like quantity control across cards and detail views, with typed `шт` and `кг` entry
- Recent cart attempt lifecycle data is now exposed through `/admin/status`, rendered in the admin dashboard, and logged with explicit attempt IDs
- The cart regression suite now covers immediate success, pending transitions, quantity routes, and the admin diagnostics payload in one repeatable command
- The repo now has a current lightweight cart UI sanity helper and a verification artifact that records both automated cart diagnostics checks and browser/manual limitations

---

## v1.10 Scraper Freshness & Reliability (Shipped: 2026-04-05)

**Phases completed:** 4 phases, 11 plans, 0 tasks

**Key accomplishments:**

- A machine-readable cycle-state contract now exists before merge and is visible through admin status
- Sale sessions now survive transient misses and only close after 60 healthy minutes of confirmed absence
- Notifier and backend “new products” surfaces now follow confirmed session reentry instead of first-ever-seen product IDs
- The scheduler now runs full cycles on a 5-minute target and green-only refreshes on a 1-minute target between them
- Per-source freshness is now visible in backend payloads and the MiniApp reuses its existing warning surface for stale-color alerts
- Scheduler cadence and freshness contracts are now protected by repeatable regression tests
- The main sale screen now hydrates from the last good payload so users see useful content before the fresh network fetch completes
- Card enrichment now runs with lower pressure and cached weight reuse so the grid stays more responsive while metadata loads
- The milestone kept the current data path and improved it directly instead of adopting a private API without clear evidence
- Cart add no longer fakes sold-out removal on timeout; the UI fails fast and can recover success from confirmed cart state
- A repeatable milestone regression command now covers continuity, notifier, scheduler freshness, admin payloads, and existing backend behavior together
- The milestone now has inspectable verification artifacts showing what was tested, what passed, and what residual risk remains
- The milestone’s continuity, freshness, warning, and main-screen performance changes are now backed by inspectable verification artifacts

---

## v1.9 Catalog Coverage Expansion (Shipped: 2026-04-04)

**Phases completed:** 3 phases, 5 plans, 0 tasks

**Key accomplishments:**

- A source-based discovery pipeline now scrapes VkusVill catalog sources into separate temp files and validates completion per source
- Catalog discovery now has admin run/status endpoints and dedicated regression coverage for the source-state contract
- Phase 36 source files are now merged into one deduped discovery artifact and additively backfilled into `category_db.json`
- Newly discovered products now flow into `product_catalog`, and the merge/backfill contract is covered by tests
- A repeatable parity query set and live-vs-local parity report now verify that newly backfilled products are searchable locally

---

## v1.8 History Search Completeness (Shipped: 2026-04-04)

**Phases completed:** 2 phases, 5 plans, 8 tasks

**Key accomplishments:**

- History search now treats active queries as full local-catalog lookups while preserving live-sale enrichment and explicit filter semantics
- HistoryPage now clears stale group/subgroup scope only when it actually switches between history mode and active search
- A targeted pytest suite now locks the History search contract against regressions across live, historical, and catalog-only matches
- History search cards now call out whether a match is live, historical, or catalog-only without changing the existing card layout
- Mixed History search result states are now protected by lightweight frontend tests alongside the existing backend search contract suite

---

## v1.7 Categories & Subgroups (Shipped: 2026-04-03)

**Phases completed:** 5 phases (29-33), shipped across 18 commits

**Key accomplishments:**

- Scraped and persisted VkusVill group/subgroup hierarchy for 16.4K products, including 524 subgroups across 46 groups
- Added main-page group → subgroup drill-down with correct product filtering
- Added exact group/subgroup favorites backed by `favorite_categories` keys like `group:X` and `subgroup:X/Y`
- Added history-page group/subgroup filters and fixed the live empty-subgroup mismatch by aligning chips with history-backed data
- Added Telegram notifications for favorited groups/subgroups with per-product dedupe and visible match reasons

---

## v1.6 Green Scraper Robustness (Shipped: 2026-04-02)

**Phases completed:** 2 phases (27-28), implemented ad-hoc

**Key accomplishments:**

- Replaced fragile green-modal loading with CDP network-aware pagination tracking
- Added live_count vs scraped_count validation gates to preserve good snapshots on bad runs
- Surfaced mismatch warnings in scheduler logs while keeping the green pipeline resilient on EC2

---

## v1.5 History Search & Polish (Shipped: 2026-04-01)

**Phases completed:** 3 phases (24-26), 10 commits

**Key accomplishments:**

- Fixed exact name search: normalize non-breaking spaces (U+00A0) and curly quotes from VkusVill copy-paste
- Added fuzzy Cyrillic search: single-character substitution fallback (е↔а, а↔о, и↔ы, ё↔е) — 300ms for typo queries
- Lazy image enrichment: populates missing product images from scraped JSON files with 5-min cache, persists to DB
- History page image coverage improved from 3.4% to ~70-80%

---

## v1.4 Proxy Centralization (Shipped: 2026-04-01)

**Phases completed:** 3 phases (21-23), 2 plans

**Key accomplishments:**

- Unified all VkusVill-facing traffic through ProxyManager singleton
- Product detail, cart API, image proxy, and login flow all use proxy rotation
- Dead proxy auto-eviction with HEAD health checks

---

## v1.2 Price History (Shipped: 2026-04-01)

**Phases completed:** 6 phases (13-18)

**Key accomplishments:**

- Built sale history database tracking 16,419 products with sale_appearances and sale_sessions tables
- Prediction engine with time/day patterns, confidence scoring, and "wait for better deal" advice
- Full history API: paginated list with search, filters (green/red/yellow/favorites/predicted_soon), sort
- History detail page: 3-column layout with calendar heatmap, confidence gauge, day/hour charts, sale log
- Interactive favorites with heart buttons, filter chips with count badges, case-insensitive Cyrillic search
- Auto-deploy infrastructure: GitHub webhook → EC2 auto-pull (~3s), Vercel auto-deploy (~15s)

---

## v1.0 Bug Fix & Stability (Shipped: 2026-03-31)

**Phases completed:** 9 phases, 5 plans, 9 tasks

**Key accomplishments:**

- No code changes needed.
- No functional code changes needed.
- Removed 3 phantom-item bugs: live_count inflation, basket IS_GREEN=1 new-item injection, and stale modal data preservation

---

## v1.0 Bug Fix and Stability (Shipped: 2026-03-30)

**Phases completed:** 8 phases, 4 plans, 6 tasks

**Key accomplishments:**

- No code changes needed.
- No functional code changes needed.

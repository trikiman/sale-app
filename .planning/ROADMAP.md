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
- ✅ **v1.13** Instant Cart & Reliability — Phases 47-51 (shipped 2026-04-16)
- ✅ **v1.14** Cart Truth & History Semantics — Phases 52-55 (shipped 2026-04-21)
- ✅ **v1.15** Proxy Infrastructure Migration — Phase 56 (shipped 2026-04-23)
- ✅ **v1.17** VLESS Timeout Hardening — Phase 57 (shipped 2026-04-25)
- ✅ **v1.18** Geo Resolver & Scraper Recovery — Phase 58 (shipped 2026-04-25)
- ✅ **v1.19** Production Reliability & 24/7 Uptime — Phases 59-61 (shipped 2026-05-05)
- ✅ **v1.20** Cart-Add Latency & User-Facing Responsiveness — Phases 62-66 + 66.1/.2/.3 (shipped 2026-05-12, tag `v1.20`)
- ✅ **v1.21** VLESS Pool Self-Healing & Reload Pipeline — Phases 67-69 (shipped 2026-05-12, tag `v1.21`)
- ⏳ **v1.22** UX Debt Cleanup + Tooling Polish — Phases 70-73 (active, started 2026-05-12)

## v1.22 UX Debt Cleanup + Tooling Polish (ACTIVE — started 2026-05-12)

Three UI/API bugs that have been sitting in `.planning/todos/pending/` since earlier milestones shipped half the fix but never closed the UI loop. Plus one tooling polish (`/gsd-check-todos` priority-aware triage). Small per-phase scope (~20-100 LOC each), tight milestone discipline preserved from v1.21.

Driving evidence (from pending todos):

| Area | Todo | Age | v1.22 Phase |
|---|---|---|---|
| History search | `2026-04-02-history-search-shows-all-matching-products-from-catalog` — search filters out products currently on sale if they match query, only shows history-only items | ~40 days | Phase 70 |
| Stale banner UX | `2026-04-06-clarify-stale-banner-freshness-vs-updated-time` — "Обновлено: 09:36" + stale warning looks contradictory to user | ~36 days | Phase 71 |
| Admin badge | `2026-05-10-v1-16-admin-html-bug-reports-badge-missing` — Phase 61 Success Criterion 3 never wired in admin.html | ~2 days | Phase 72 |
| Kiro tooling | `2026-05-12-update-gsd-check-todos-skill` — flat list, no priority sort, no multi-select | 0 days | Phase 73 |

**Goal:** Close accumulated UX/UI debt from v1.5 / v1.10 / v1.16, plus a tooling polish so future milestones triage todos faster.
**Granularity:** Small
**Phases:** 4 (70-73)
**Requirements:** 7 (3 UX, 1 TOOL, 3 OPS)

### Phases

- [ ] **Phase 70: History Search Catalog-Wide** — Remove the `total_sale_count > 0` filter from `/api/history/search` so ANY product in `product_catalog` matching the query is returned. Result rows carry `currentSaleType: "green" | "red" | "yellow" | null` so `HistoryPage.jsx` can render live badges on history cards that match today's sale. Search behaves like VkusVill's own search: every matching product visible, live-vs-history differentiated by visual treatment. Smoke gate: seeded test against "цезарь" with a fixture green product → result includes the green product with `currentSaleType: "green"`. (UX-BUG-01)

- [ ] **Phase 71: Stale Banner Clarification** — Align the UI's "Обновлено: HH:MM" label with the per-source stale banner so they don't contradict. Pick option (A) switch header label to oldest-source-time, or (B) inline-annotate banner with "(green: 30m old)". Discuss → plan → ship in one phase. Re-examine the 10-minute stale threshold constant if v1.10 cadence changes suggest it's wrong. Smoke gate: synthetic fixture with green mtime 25 min old, red + yellow fresh → banner AND header both reflect the stale source. (UX-COPY-01)

- [ ] **Phase 72: admin.html Bug Reports Badge** — Add ~20 lines to `backend/admin.html` mirroring the existing `proxy-badge` (line 426) / `cart-pending-count` (line 407) patterns: new `<span id="bug-reports-badge">` hidden by default, `applyStatus(data)` reads `data.bugReports.count/unread`, shows `Bug Reports (N)` when N > 0, optional click opens `/admin/bug-reports`. Backend side shipped in v1.16 (`/admin/status.bugReports.{count,unread}`), this is pure UI. If v1.21 `xray_drift` card makes sense to add in the same file for the same cost, include it as UX-BADGE-02 late-insert. Smoke gate: curl `/admin/status` mock with `bugReports.count=3,unread=2` → admin.html contains `Bug Reports (2)` badge string. (UX-BADGE-01)

- [ ] **Phase 73: gsd-check-todos Skill Polish** — Kiro-side skill file edits under `~/.kiro/skills/gsd-check-todos/SKILL.md` and `~/.kiro/get-shit-done/workflows/check-todos.md`. Adds `priority: P1|P2|P3|P4` frontmatter (existing defaults to P3), sorts list P1 → P4 then age, adds `--by-area` flag. New action: `fold into milestone` — when no active milestone, prompt `/gsd-new-milestone` with selected todo scopes pre-filled. Documents frontmatter schema explicitly. Updates all 4 current pending todos with explicit priority values. No EC2 deploy. Smoke gate: running the updated skill against a synthetic 5-todo directory returns them in P1-first order, and the `fold into milestone` option appears. (TOOL-01)

### Phase Details

### Phase 70: History Search Catalog-Wide
**Goal:** Fix v1.5 regression where searching history for a product currently on sale returns no results because the filter excludes `total_sale_count == 0` items that never had a sale recorded but exist in `product_catalog`.
**Depends on:** v1.21 closed (no new VLESS infra, just a backend filter removal + miniapp rendering tweak); v1.21 regression gate must stay green.
**Requirements:** UX-BUG-01 — plus continued OPS-15/16/17.
**Success Criteria:**
  1. [ ] `/api/history/search?q=...` returns products from `product_catalog` matching the query regardless of `total_sale_count`. Existing sort (relevance) preserved.
  2. [ ] Response rows carry `currentSaleType: str | null` derived from the latest merged products set (green/red/yellow). `null` when product is not on sale today.
  3. [ ] `miniapp/src/HistoryPage.jsx` renders currently-on-sale matches with the same green/red/yellow badge as `App.jsx` main page; history-only matches keep ghost-card treatment.
  4. [ ] Regression pin: `backend/test_history_search_catalog_wide.py` seeds a catalog row for "цезарь салат" with `total_sale_count=0` AND a current green sale for the same product id, asserts the search returns it with `currentSaleType == "green"`.
  5. [ ] v1.21 + v1.20 + v1.19 smoke scripts stay green.
**Plans:** TBD via `/gsd-plan-phase 70`

### Phase 71: Stale Banner Clarification
**Goal:** Stop showing a freshly-updated header timestamp next to a stale-source warning without explaining the semantic difference. User-reported confusion since v1.10.
**Depends on:** Phase 70 (not strictly, but phases 70/71 share the miniapp build).
**Requirements:** UX-COPY-01 — plus continued OPS-15/16/17.
**Success Criteria:**
  1. [ ] Pick option A OR B (see REQUIREMENTS.md UX-COPY-01) — decision captured in 71-CONTEXT.md during `/gsd-discuss-phase 71`. Default leaning: option (B) inline-annotate banner, since it keeps the `Обновлено` label's "latest merged payload" semantic intact and user can see per-source staleness directly in the warning.
  2. [ ] Copy clarifies `Обновлено` vs the per-source stale banner without requiring user to read help text — one-sentence banner addition is enough.
  3. [ ] 10-minute source-stale threshold re-verified against current green/red/yellow cadence (cron every ~5 min). If wrong, adjust the constant; if right, document the check in 71-VERIFICATION.md.
  4. [ ] Regression pin: `miniapp/src/__tests__/stale-banner.test.jsx` asserts banner contains per-source age text when at least one source is stale.
  5. [ ] Live MCP check via Chrome DevTools: page with synthetic stale fixture shows banner AND header both reflecting the stale source, screenshot captured.
**Plans:** TBD via `/gsd-plan-phase 71`

### Phase 72: admin.html Bug Reports Badge
**Goal:** Ship the v1.16 Phase 61 Success Criterion 3 UI side — backend has the counts for 2 weeks already.
**Depends on:** nothing from v1.22 (independent, smallest phase).
**Requirements:** UX-BADGE-01 — plus continued OPS-15/16/17. Optionally folds in UX-BADGE-02 (v1.21 `xray_drift` card) if cheap.
**Success Criteria:**
  1. [ ] `backend/admin.html` gains `<span id="bug-reports-badge" class="badge" hidden>Bug Reports (0)</span>` placed next to `proxy-badge` in the status row.
  2. [ ] `applyStatus(data)` updates badge text from `data.bugReports.unread` (fallback `data.bugReports.count`), toggles `hidden` attribute when count is 0.
  3. [ ] Badge click navigates to `/admin/bug-reports` (existing endpoint).
  4. [ ] Smoke gate: curl `/admin/status` with `-H "X-Admin-Token: $T"` against EC2 returns `bugReports.count >= 0`; assert admin.html at HEAD contains the badge span.
  5. [ ] Optional UX-BADGE-02 late-insert: if adding a small `xray_drift` card is <10 LOC using the same `applyStatus` hook, do it. Otherwise defer to v1.23.
**Plans:** TBD via `/gsd-plan-phase 72`

### Phase 73: gsd-check-todos Skill Polish
**Goal:** Make todo triage take minutes, not a file-by-file read. Priority sort + fold-into-milestone action.
**Depends on:** nothing (skill file edits only, no product code change).
**Requirements:** TOOL-01 — plus continued OPS-15/16/17 (cross-cutting; no EC2 smoke needed for this phase).
**Success Criteria:**
  1. [ ] `priority: P1|P2|P3|P4` frontmatter documented + recognized by the skill; todos missing the field default to P3.
  2. [ ] List output sorted P1 → P4, then by age (oldest first within priority). Flag: `--by-area` groups by area instead.
  3. [ ] New action `fold into milestone` in the skill's action menu: when no active milestone, routes to `/gsd-new-milestone` with selected todos pre-filled as requirements-seed; when active milestone, prompts user to add as phase or to stack in `v2 requirements` section.
  4. [ ] The 4 currently pending todos updated in-place with explicit priority:
     * `2026-04-02-history-search-...` → P2 (consumed into v1.22 UX-BUG-01)
     * `2026-04-06-clarify-stale-banner-...` → P3 (consumed into v1.22 UX-COPY-01)
     * `2026-05-10-v1-16-admin-html-bug-reports-badge` → P2 (consumed into v1.22 UX-BADGE-01)
     * `2026-05-12-update-gsd-check-todos-skill` → P4 (this phase itself)
  5. [ ] Three "consumed" todos move to `.planning/todos/completed/` when their corresponding v1.22 phase ships.
  6. [ ] Frontmatter schema documented in `~/.kiro/skills/gsd-check-todos/SKILL.md` — `priority`, `area`, `files`, `created` explicit with valid values.
**Plans:** TBD via `/gsd-plan-phase 73`

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

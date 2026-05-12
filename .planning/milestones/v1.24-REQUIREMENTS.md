# Requirements — v1.24 Pool Self-Heal Hardening + Outage UX

## Milestone Goal

Eliminate the ~1 hour family-facing outage pattern observed 2026-05-13. When VLESS pool collapses, recovery must take minutes not an hour, and during the rebuild window users must see cached data with stale badges instead of an empty "0 всего" grid. Pair this with codifying the style guide v2 rules from 2026-05-13 into automated lint checks so UX regressions like the header visual-weight violation get caught in CI.

Three pending todos surfaced during v1.23 verification:
- P1 `2026-05-13-vless-pool-slow-recovery-1h-outage.md` — 60-min recovery time, no quarantine memory, no refresh throttle, no operator alert
- P2 `2026-05-13-empty-grid-when-all-sources-stale-during-pool-recovery.md` — v1.22 phantom-strip hides cached data when all 3 sources stale
- Style guide v2 (docs/miniapp-ui-style-guide.md, committed `91a6e30`) — enforcement checklist needs automated tooling

Scope intentionally tight (matches v1.21/v1.22/v1.23 discipline) — 3 phases, small.

Driving evidence:
- **16:19 → 17:30 MSK 2026-05-13**: VLESS pool collapsed (20 quarantined, 0 healthy). Self-heal loop parsed 519 nodes → 231 RU → probed them 19 times in 15 min, wasted work because no quarantine memory across refreshes
- User observation: "grid is back but it so bad when cusite didnt work around 1 hour"
- `/api/health/deep` during incident: `status: degraded, pool.size: 0, quarantined_count: 20, reasons: ["pool_below_min_healthy:0_lt_7"]`
- MiniApp during incident: `📦 0 всего 🟢 0 🔴 0 🟡 0` despite `data/proposals.json` having 174 cached products (16/35/123)
- Header visual-weight violation surfaced via screenshot — "Выйти" green-tinted while sibling controls stay neutral, no explicit rule in style guide v1

## Requirements

### Pool Self-Heal Hardening

- [ ] **REL-16**: VLESS pool refresh uses persistent quarantine memory. When a node probes as dead, it's added to `data/pool_quarantine.json` with a TTL (default 20 min). Subsequent refreshes skip nodes in quarantine. Probe time drops from ~3 min (probe all 231) to ~30 s (probe only unknown-state nodes). Measured via `pool_refresh_complete` JSONL event `duration_ms` field.

- [ ] **REL-17**: Refresh throttle — minimum 60 s between full refreshes. If a scrape fails and pool is already refreshing or just refreshed within the last 60 s, scraper backs off instead of triggering another refresh. Prevents the 19-refreshes-in-15-min thrash observed 2026-05-13. Implemented in `vless/manager.py::ensure_pool`.

- [ ] **REL-18**: Lower-water-mark earlier warning — `min_healthy` check fires at `size ≤ 10` (currently 7). Rate-of-decline check: if pool lost 3+ nodes in 5 min, trigger proactive refresh even if still above 7. Catches collapse earlier, less time in degraded state.

- [ ] **REL-19**: Scheduler graceful degrade — when pool is 0 for >2 min, scraper skips the cycle (exit 0 with "skipped_pool_dead" outcome) instead of failing with exit 1. Emits `scheduler_pool_dead` JSONL event. Reduces log noise, makes dashboards truthful, frees CPU for pool refresh to complete faster.

### Outage UX

- [ ] **UX-STALE-01**: When all 3 source colors stale simultaneously, `/api/products` endpoint returns the last-good snapshot from `proposals.json` with a `stale_all: true` flag instead of stripping products. Client shows cached products with per-card `⏳ stale` badge. Fixes the "empty grid" observed 2026-05-13 when pool rebuilt. Pairs with REL-19.

- [ ] **UX-STALE-02**: Stale banner UI upgraded from the thin yellow line to a prominent bordered card (per style guide v2 "State Patterns > Stale" section). Message includes per-source age + estimated recovery time: "Данные устарели. Источники: зелёные (25 мин), красные (27 мин), жёлтые (27 мин). Показаны последние известные цены. Обновление через ~N мин." Banner visible above the fold on mobile.

### Style Guide v2 Enforcement

- [ ] **TOOL-02**: `stylelint` config rejects off-scale `padding`/`margin`/`gap` values. Only `4/8/12/16/24/32/48` (via CSS var or literal) allowed. Stylelint runs in `npm run lint` and on pre-commit. Catches future visual-drift regressions at the file-save layer.

- [ ] **TOOL-03**: ESLint rule rejects inline `style=` attribute in JSX (`react/forbid-dom-props` configured with `style` in the forbid list). Forces CSS class usage per style guide v2 rule. Exceptions require explicit ESLint disable comment with justification.

### Operations — Continuity

- [ ] **OPS-21**: `scripts/verify_v1.24.sh` chains `verify_v1.23.sh all` and adds Phase 77/78/79 smoke checks. Grows phase-by-phase.

- [ ] **OPS-22**: Each v1.24 phase includes live MCP verification where UI surface is affected. For pool phases, live simulate pool death (`echo "[]" > data/pool.json && systemctl restart saleapp-scheduler`) and measure recovery time via `/api/health/deep` polling.

- [ ] **OPS-23**: Cross-version regression gate green — `bash scripts/verify_v1.23.sh all` (which chains back to v1.19) passes post-deploy. All v1.24 changes additive.

### Observability — Late consideration

- [ ] **OBS-08** (conditional, may defer): Telegram admin alert when pool size stays at 0 for >10 min. Wires into existing `bot/notifier.py`. Only fires once per incident with 30-min cooldown. Addresses v1.19 REL-FUT-05 tech debt. **Decision: ship only if Phase 77/78 trivially absorbs this; otherwise defer to v1.25 observability milestone.**

## v2 Requirements

### Carried forward from v1.19

- **REL-FUT-01..08, OBS-FUT-01..03** — same list as v1.23 audit.

### Carried forward from v1.20

- Phase 64 HAR capture + `FAST_CART_ADD_URL` go/no-go decision
- Phase 65 NEEDS_OPERATOR-1 Playwright slow-path test
- Phase 66 `_cart_add_attempts` TTL extension for true 1h p95 accuracy

### Carried forward from v1.21 tech debt

- `XRAY_RESTART_THROTTLE_S = 90.0` is in-memory only
- `_DRIFT_FIRST_SEEN` is in-process; each backend worker has its own clock

### Carried forward from v1.22 tech debt

- Vitest/RTL wiring for miniapp (style guide v2 review checklist would catch more regressions if snapshot tests existed)
- Multi-select fold-into-milestone in `/gsd-check-todos`
- Richer admin UI for individual bug reports

### Carried forward from v1.23 tech debt

- Background pre-warm of top-visible product details (deferred from PERF-10 decision; still not measured to be needed)
- Lighthouse synthetic for main page CLS (declined in Phase 75 in favor of direct DOM measurement; revisit if regression lands)
- Live click-through NEEDS_OPERATOR for cart trash button (Telegram-phone verification pending)

## Out of Scope

| Feature | Reason |
|---|---|
| Full VLESS provider migration | REL-16/17/18 harden the current igareck pipeline; provider switch is a bigger separate decision |
| Pool node scraping from new sources | Same reason — stick with igareck for this milestone |
| Dark/light theme re-audit of full miniapp | Style guide v2 codifies rules; systematic audit is a separate polish phase |
| Vitest wiring for miniapp | v1.22 tech debt, still deferred; style guide v2 enforcement via stylelint + eslint is the interim measure |
| Background pre-warm of product details | v1.23 out-of-scope, still measuring if PERF-10 alone is sufficient |
| SSE `/api/stream` graceful-shutdown | Infrastructure-layer, separate from pool/UX |

## Traceability

(Provisional phase mapping; finalized by `/gsd-roadmapper`.)

| Requirement | Provisional Phase | Status |
|---|---|---|
| REL-16 | Phase 77 (Quarantine memory + deadlist) | Defined |
| REL-17 | Phase 77 (refresh throttle — pairs with REL-16) | Defined |
| REL-18 | Phase 77 (lower-water-mark — same file) | Defined |
| REL-19 | Phase 77 (scheduler graceful degrade) | Defined |
| UX-STALE-01 | Phase 78 (backend flag + frontend rendering) | Defined |
| UX-STALE-02 | Phase 78 (banner UI upgrade — same feature surface) | Defined |
| TOOL-02 | Phase 79 (stylelint config) | Defined |
| TOOL-03 | Phase 79 (eslint rule) | Defined |
| OPS-21/22/23 | All phases (cross-cutting) | Defined |
| OBS-08 | Conditional — fold into 77 if trivial, else defer | Conditional |

**Coverage:**
- v1.24 requirements: 9 total (4 REL, 2 UX, 2 TOOL, 1 optional OBS)
- Mapped to phases: 9 (provisional, 3 phases + 1 cross-cutting)
- Unmapped: 0 ✓

## Prior Milestone — Archived

v1.23 Detail-Path Performance + UX Polish shipped 2026-05-13 with 7/7 requirements + 1 late insert (UX-CART-02 clear-cart desktop Chrome fallback) across 3 phases (74/75/76). Full archive:
- `.planning/milestones/v1.23-ROADMAP.md`
- `.planning/milestones/v1.23-REQUIREMENTS.md`
- `.planning/milestones/v1.23-MILESTONE-AUDIT.md`
- `.planning/milestones/v1.23-phases/{74,75,76}-*/`
- Git tag `v1.23`, commits `e5574f3..91a6e30` (10 commits including milestone audit and style guide v2 upgrade)
- Cold-path `/api/product/{id}/details` p95 dropped from ~16s → 0.678s (25× improvement)
- Card grid layout shift eliminated via `min-height: 36px` lock
- Cart panel trash button shipped + Очистить desktop Chrome fallback fixed

The v1.19 + v1.20 + v1.21 + v1.22 + v1.23 smoke scripts retained as cross-version regression guards; v1.24 adds `scripts/verify_v1.24.sh`.

---
*Requirements defined: 2026-05-13*
*Prior milestone v1.23 archived 2026-05-13*

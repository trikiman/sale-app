# Requirements — v1.22 UX Debt Cleanup + Tooling Polish

## Milestone Goal

Clear the accumulated UX debt across earlier milestones that never made it into a dedicated phase. Three UI/API bugs have been sitting in `.planning/todos/pending/` for weeks, each small on its own but visible to family-scale users every day. Plus one tooling polish for `/gsd-check-todos` so future milestone triage takes minutes instead of reading every todo file.

v1.20 shipped reliability. v1.21 shipped self-healing infrastructure. v1.22 shipps the UI catching up to v1.5 / v1.10 / v1.16 backends that already solved half the problem.

Continue the v1.19 / v1.20 / v1.21 robust-over-fast cultural commitment: every phase ships with a scripted test, a `VERIFICATION.md`, rollback rehearsal, and a cross-version regression gate against the v1.21 smoke script (which chains into v1.20 + v1.19).

Driving evidence (from `.planning/todos/pending/`):

- `2026-04-02-history-search-shows-all-matching-products-from-catalog.md` — v1.5 regression. History search filters to `total_sale_count > 0` only, so a product that IS currently on sale AND matches the search can be absent from results. User searches "цезарь", salad is on sale right now, salad doesn't appear, user thinks the product is missing. Backend `product_catalog` table has 16 K seeded rows but the filter hides them.
- `2026-04-06-clarify-stale-banner-freshness-vs-updated-time.md` — v1.10 gap. MiniApp can show `Обновлено: 09:36` (latest merged payload time) alongside the stale-data banner (per-source file mtime > 10 min). The two timestamps mean different things but the UI doesn't explain the difference. Users see "freshly updated + warning" and correctly call it confusing.
- `2026-05-10-v1-16-admin-html-bug-reports-badge-missing.md` — v1.16 gap. Phase 61 Success Criterion 3 required a Bug Reports (N) badge in `admin.html`. Backend ships the counts (`bugReports.count` + `bugReports.unread`) but the admin UI has zero references. Verified by grep at commit HEAD. Small cosmetic fix (~20 LOC) mirroring the existing `proxy-badge` pattern.
- `2026-05-12-update-gsd-check-todos-skill.md` — tooling. Current `/gsd-check-todos` prints a flat list with no priority, no roadmap correlation, no multi-select. Triage is slow when 5+ todos are open. Add priority frontmatter + P1-first sort + fold-into-milestone action.

## Requirements

### UX Debt — Data Surface

- [ ] **UX-BUG-01**: `/api/history/search?q=...` returns ALL products from `product_catalog` that match the query, not just history items with `total_sale_count > 0`. Result rows carry a new `currentSaleType` field (`"green" | "red" | "yellow" | null`) so the frontend can render live badges next to history cards. MiniApp `HistoryPage.jsx` renders currently-on-sale matches with the same color treatment as the main page (green/red/yellow badge), history-only matches keep ghost-card styling. Search UX matches VkusVill's own: all matching products visible regardless of sale state.

- [ ] **UX-COPY-01**: Stale banner and updated-time header are semantically aligned. Pick ONE of:
  * (A) Header label switches to oldest-source-time (matches banner basis), OR
  * (B) Banner surfaces which source is stale and by how much, inline next to the warning.
  
  Decision made in `/gsd-discuss-phase 71` with a quick user check. Ship whichever option the user picks. Copy clarifies that "Обновлено" is merged-payload time, not per-source freshness. If the 10-minute stale threshold needs retuning after v1.10 green/red/yellow cadence changes, adjust the constant in the same phase.

- [ ] **UX-BADGE-01**: `backend/admin.html` renders a `Bug Reports (N)` badge in the status row, hidden when count is 0, visible with unread count when greater. Click navigates to `/admin/bug-reports` (existing endpoint). Implementation mirrors existing `proxy-badge` pattern (lines 426-427) and `cart-pending-count` pattern (line 407). No new backend work — `/admin/status.bugReports.{count,unread}` is already exposed.

### Tooling Polish

- [ ] **TOOL-01**: `/gsd-check-todos` skill adds priority-aware triage. Concrete scope:
  * `priority: P1|P2|P3|P4` frontmatter field (existing todos default to P3).
  * List sorted P1 → P4, then by age. Flag: `--by-area` groups instead.
  * New action: `fold into milestone` — when no active milestone, prompt `/gsd-new-milestone` with selected todo scopes pre-filled. When active, prompt user to add as phase.
  * Document the frontmatter schema in `~/.kiro/skills/gsd-check-todos/SKILL.md` (currently implicit).
  * Update existing pending todos in-place with explicit priority values.

### Operations — v1.19/v1.20/v1.21 Continuity

- [ ] **OPS-15**: `scripts/verify_v1.22.sh` is created alongside v1.19/v1.20/v1.21 smoke scripts. `verify_v1.22.sh all` chains `verify_v1.21.sh all` at the end (which already chains v1.20 + v1.19). Grows phase-by-phase with checks per UX-BUG-01, UX-COPY-01, UX-BADGE-01, TOOL-01. Expected 4-6 new checks minimum.

- [ ] **OPS-16**: Every v1.22 phase includes end-to-end verification on EC2 where applicable (UX-BUG-01 needs backend deploy + real data, UX-COPY-01 needs live miniapp check via Chrome DevTools MCP, UX-BADGE-01 needs admin.html deploy + auth), or local-only where EC2 is not needed (TOOL-01 is Kiro-side only). Rollback rehearsal per phase.

- [ ] **OPS-17**: Cross-version regression gate stays green — `bash scripts/verify_v1.21.sh all` (which includes v1.20 + v1.19 chain) must pass post-deploy. Every v1.22 change is additive to existing contracts; any breaking change to `/api/products`, `/api/history/*`, `/admin/status`, or the miniapp build is out-of-scope and should be flagged as a late-milestone concern requiring scope-decision.

## v2 Requirements

### Carried forward from v1.19 (still deferred)

- **REL-FUT-01** — Probe failure-reason classification (DNS / TLS / HTTP-4xx / timeout)
- **REL-FUT-02** — Multi-target probe (VkusVill + ipinfo.io)
- **REL-FUT-05** — Telegram alert on breaker state changes (dedup'd) and `xray_restart_failed` events
- **REL-FUT-06** — Replenish to `MAX_CACHED` instead of `MIN_HEALTHY + 1`
- **REL-FUT-07** — Shorter cooldown for non-block failures (TLS = 15 min)
- **REL-FUT-08** — Predictive refresh when quarantine > replenish rate

### Carried forward from v1.20 tech debt

- Phase 64 HAR capture + live ablation sweep + go/no-go decision for `FAST_CART_ADD_URL` swap — scaffolding shipped in v1.20, spike work deferred (requires operator browser session)
- Phase 65 NEEDS_OPERATOR-1 Playwright slow-path test (`miniapp/tests/test_cart_slow_path.py`)
- Phase 66 `_cart_add_attempts` TTL is 30 s so `p95_1h` reflects ~30 s of traffic — bump TTL or persist resolved attempts to a bounded ring buffer for true 1 h accuracy

### Carried forward from v1.21 tech debt

- `admin.html` currently does not surface the new v1.21 `xray_drift` block — `/admin/status.reliability.xray_drift` is returned by the backend but not yet rendered in the admin UI. **Eligible for late insert into v1.22** if UX-COPY-01 / UX-BADGE-01 work touches `admin.html` anyway and a small card addition is cheap.
- Throttle `XRAY_RESTART_THROTTLE_S = 90.0` is in-memory only. Low risk at family-scale but not persisted across scheduler restarts. Reconsider if we see restart churn after v1.21 self-healing lands more widely.
- `_DRIFT_FIRST_SEEN` is in-process; each backend worker has its own clock. Currently single-worker on EC2, so fine. If we ever scale to multiple backend workers the clock would need consolidation.

## Out of Scope

| Feature | Reason |
|---|---|
| History page sort / filter dropdown beyond what UX-BUG-01 already touches | Scope creep; current UX-BUG-01 fixes the filter bug — richer controls are a different feature, separate milestone |
| Cart item optimistic-state animations | Cosmetic polish; v1.20 already closed the false-fail-then-double-add blocker |
| Subgroup "expand all" / multi-select | Different UX surface; no pending todo for it |
| admin.html theming / dark mode | Visual polish unrelated to the specific gap fix |
| Migration of `admin.html` to the miniapp React stack | Long-running refactor, separate workstream if ever needed |
| `gsd-check-todos` UI in Kiro (vs CLI-style output) | TOOL-01 is skill-file-only; IDE panel is separate scope |

## Traceability

(Provisional phase mapping; finalized by `/gsd-roadmapper`.)

| Requirement | Provisional Phase | Status |
|---|---|---|
| UX-BUG-01 | Phase 70 (History search catalog-wide) | Defined |
| UX-COPY-01 | Phase 71 (Stale banner clarification) | Defined |
| UX-BADGE-01 | Phase 72 (admin.html Bug Reports badge) | Defined |
| TOOL-01 | Phase 73 (gsd-check-todos skill polish) | Defined |
| OPS-15 | All phases (cross-cutting) | Defined |
| OPS-16 | All phases (cross-cutting) | Defined |
| OPS-17 | All phases (cross-cutting) | Defined |

**Coverage:**
- v1.22 requirements: 7 total (3 UX, 1 TOOL, 3 OPS)
- Mapped to phases: 7 (provisional, 4 phases)
- Unmapped: 0 ✓

## Prior Milestone — Archived

v1.21 VLESS Pool Self-Healing & Reload Pipeline shipped 2026-05-12 with 8/8 requirements satisfied across 3 phases (67/68/69). Full archive:
- `.planning/milestones/v1.21-ROADMAP.md`
- `.planning/milestones/v1.21-REQUIREMENTS.md`
- `.planning/milestones/v1.21-MILESTONE-AUDIT.md`
- `.planning/milestones/v1.21-phases/{67-admitted-node-self-healing-loop,68-xray-auto-reload-on-admission-change,69-drift-visibility}/`
- Git tag `v1.21`, commits `fcc740f..44fba0f` (14 commits), live-verified on EC2 2026-05-12

The v1.19 + v1.20 + v1.21 smoke scripts are retained as cross-version reliability regression guards; v1.22 adds `scripts/verify_v1.22.sh` alongside.

---
*Requirements defined: 2026-05-12*
*Prior milestone v1.21 archived 2026-05-12*

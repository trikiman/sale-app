---
gsd_state_version: 1.0
milestone: v1.21
milestone_name: VLESS Pool Self-Healing & Reload Pipeline
status: awaiting_audit
last_updated: "2026-05-12T22:00:00.000Z"
last_activity: 2026-05-12
progress:
  total_phases: 3
  completed_phases: 3
  total_plans: 9
  completed_plans: 9
  percent: 100
current_phase: 69
current_phase_status: code_shipped
current_phase_resume_file: null
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-12)

**Core value:** Family members see every VkusVill discount and can add to cart in one tap
**Current focus:** v1.21 VLESS Pool Self-Healing & Reload Pipeline — convert the manual fix from 2026-05-10 (sudo systemctl restart saleapp-xray + pool whitelist rebuild) into a deterministic self-healing loop so the next outage is caught in minutes, not days. 3 phases (67-69), 8 requirements (3 REL, 2 OBS, 3 OPS).

## Current Position

Phase: All 3 v1.21 phases code-complete and committed. Awaiting milestone audit + operator live verification.
Next step: `/gsd-audit-milestone` to produce `.planning/v1.21-MILESTONE-AUDIT.md`. STOP before `/gsd-complete-milestone` per user's standing instruction.
Status: Phase 67 shipped + live-verified on EC2 post-hotfix (4 commits). Phase 68 code shipped, awaiting operator sudoers deploy + restart-triggered proof (3 commits). Phase 69 code shipped, awaiting deploy + drift-injection proof (3 commits). Total 10 commits this milestone (67 × 4 + 68 × 3 + 69 × 3). Full test suite 355 passed + 3 baseline Windows-only failures unchanged.
Last activity: 2026-05-12 — Phase 69 three atomic commits (`0888b58`, `0a544a3`, `e3a02cd`); all v1.21 code shipped.

## Milestone Goal (v1.21 — active)

- Periodic per-node re-probe through the running bridge every ≤ 10 min, using `_probe_vkusvill` with authenticated HEAD (REL-13)
- xray auto-reload when `refresh_proxy_list` admits a host set different from the running config; sudo systemctl passwordless on saleapp-xray.service only; throttled ≤ 1 restart per 90s (REL-14)
- Per-node production success rate tracking (100-sample sliding window); nodes with success_rate < 0.1 treated as dead even if observatory says alive (REL-15)
- `/api/health/deep` + `/admin/status.reliability` `xray_drift` block with degraded (>5 min drift) and unhealthy (>10 min drift + stale cycle) thresholds (OBS-06)
- `data/proxy_events.jsonl` `pool_refresh_complete` event with admitted/added/removed host lists + restart timing + success_rate_drops (OBS-07)
- `scripts/verify_v1.21.sh` with per-phase EC2 smoke checks; chains v1.20 + v1.19 regression at the end; rollback rehearsal per phase (OPS-12/13/14)
- No regression on v1.20 reliability gains (warmup daemon, cart-items cache, bridge semaphore, idempotency index, /api/health/deep cart_add block must all still pass)
- No regression on v1.19 reliability gains (pool drift visibility, breaker, deep health endpoint, 24/24 smoke)

## Previous Milestone (v1.20 — shipped 2026-05-12)

- Cart-Add Latency & User-Facing Responsiveness — all 15 requirements satisfied + 3 late UX fixes
- 6 phases: 62 (Sessid Keep-Alive), 63 (Bridge Contention), 64 (API Surface Spike scaffolding), 65 (Frontend Polling + Idempotency), 66 (Hot-Path Observability), 66.1 (Stale-Color Phantom Strip), 66.2 (Cart Stepper Cache-Hit Fix), 66.3 (Warmup Endpoint Retune — /personal/ → basket_recalc, 3× speedup live-verified)
- Archive: `.planning/milestones/v1.20-*` (ROADMAP, REQUIREMENTS, MILESTONE-AUDIT, SESSION-REPORT, v1.20-phases/ ×8)
- Git: commits `51888f7..4890bd0`, tag `v1.20` pushed to origin

## Next Up

- `/gsd-audit-milestone` to produce `.planning/v1.21-MILESTONE-AUDIT.md` — check all 8 requirements satisfied in code, map requirements → phase deliverables → live-verification status
- **STOP before `/gsd-complete-milestone`** per user's standing instruction — await manual review before archiving
- Operator: deploy sudoers file per `.planning/phases/68-xray-auto-reload-on-admission-change/68-VERIFICATION.md` NEEDS_OPERATOR-1 then run full `bash scripts/verify_v1.21.sh all` on EC2
- v1.22 candidate milestone: UX debt cleanup (admin Bug Reports badge, stale-banner copy, history search unrestricted mode) — 3 pending todos in `.planning/todos/pending/`

## Completed Milestones

| Milestone | Phases | Shipped |
|-----------|--------|---------|
| v1.0 Bug Fix & Stability | 1-9 | 2026-03-31 |
| v1.1 Testing & QA | 10-12 | 2026-03-31 |
| v1.2 Price History | 13-18 | 2026-04-01 |
| v1.3 Performance & Optimization | 19-20 | 2026-04-01 |
| v1.4 Proxy Centralization | 21-23 | 2026-04-01 |
| v1.5 History Search & Polish | 24-26 | 2026-04-01 |
| v1.6 Green Scraper Robustness | 27-28 | 2026-04-02 |
| v1.7 Categories & Subgroups | 29-33 | 2026-04-03 |
| v1.8 History Search Completeness | 34-35 | 2026-04-04 |
| v1.9 Catalog Coverage Expansion | 36-38 | 2026-04-04 |
| v1.10 Scraper Freshness & Reliability | 39-42 | 2026-04-05 |
| v1.11 Cart Responsiveness & Truth Recovery | 43-45 | 2026-04-06 |
| v1.12 Add-to-Cart 5s Hard Cap | 46 | 2026-04-08 |
| v1.13 Instant Cart & Reliability | 47-51 | 2026-04-16 |
| v1.14 Cart Truth & History Semantics | 52-55 | 2026-04-21 |
| v1.15 Proxy Infrastructure Migration | 56 | 2026-04-23 |
| v1.17 VLESS Timeout Hardening | 57 | 2026-04-25 |
| v1.18 Geo Resolver & Scraper Recovery | 58 | 2026-04-25 |
| v1.19 Production Reliability & 24/7 Uptime | 59-61 | 2026-05-05 |
| v1.20 Cart-Add Latency & User-Facing Responsiveness | 62-66 + 66.1/.2/.3 | 2026-05-12 |

## Accumulated Context

- v1.20 shipped: 20-min keepalive daemon + on-open warmup nudge (PERF-03/04/05), per-user cart-items 12s cache + global scraper semaphore (PERF-06/07), USE_FAST_CART_ADD_ENDPOINT feature-flag scaffolding (PERF-08/09), frontend client_request_id idempotency + 5s AbortController + polling-on-abort (UX-01/02/03), /api/health/deep cart_add block + data/cart_events.jsonl 11-key ledger (OBS-04/05), scripts/verify_v1.20.sh with 19 smoke checks + v1.19 regression gate, 66.1 stale-color filter dropping phantom products, 66.2 cache-hit stepper UI fix, 66.3 warmup endpoint swap /personal/ → basket_recalc (3x speedup)
- v1.19 shipped: pre-flight VLESS probe + 3-state breaker + /api/health/deep + pool drift visibility
- v1.18 shipped: 3-provider geo resolver (ipinfo → ipapi → ip-api), scraper CDP-WS recovery helpers, +15 tests
- v1.17 shipped: xray policy + observatory + leastPing, remove_proxy rotation, egress geo verification
- v1.15 shipped: VLESS+Reality migration via xray-core bridge (socks5://127.0.0.1:10808)
- 2026-05-10 outage manual fix: `sudo systemctl restart saleapp-xray` after pool whitelist rebuild → bridge HTTP 000 → HTTP 200 immediately, scheduler recovered within 2 min. Root cause of 4-day outage: (1) admitted nodes never re-probed, (2) xray never reloaded config after admission rewrite. Both root causes consumed into v1.21 REL-13/14/15.

### Pending Todos (see `.planning/todos/pending/`)

- **[P2]** `2026-05-10-v1-16-admin-html-bug-reports-badge-missing` — v1.16 gap: backend exposes counts, admin.html never wired. Candidate for v1.22.
- **[P3]** `2026-04-06-clarify-stale-banner-freshness-vs-updated-time` — partially resolved by 66.1; UX copy refinement remains. Candidate for v1.22.
- **[P3]** `2026-04-02-history-search-shows-all-matching-products-from-catalog` — v1.5 search filter too restrictive. Candidate for v1.22.
- **[P4]** `2026-05-12-update-gsd-check-todos-skill` — tooling: add priority/roadmap-correlation/multi-select to `/gsd-check-todos`. Nice-to-have, not blocking.

## Known Bugs

- (none open — v1.20 closed the stale-color phantom, cart stepper ⟲ flash, and warmup endpoint choice bugs)

## Timeline

| Event | Date |
|-------|------|
| v1.14 milestone closed and archived | 2026-04-22 |
| v1.15 shipped (VLESS proxy migration) | 2026-04-23 |
| v1.17 shipped (VLESS timeout hardening) | 2026-04-25 |
| v1.18 shipped (geo resolver + scraper recovery) | 2026-04-25 |
| v1.19 shipped + archived | 2026-05-05 |
| 4-day VLESS outage (pool.json healthy, xray routing to dead May 5 outbound) | 2026-05-06 → 05-10 |
| Manual fix: sudo systemctl restart saleapp-xray + pool whitelist rebuild | 2026-05-10 |
| Root-cause todos written (REL-13/14/15 + OBS-06/07 seed) | 2026-05-10 |
| v1.20 milestone STARTED | 2026-05-05 |
| v1.20 milestone SHIPPED + ARCHIVED + TAGGED | 2026-05-12 |
| v1.21 milestone STARTED (VLESS Pool Self-Healing & Reload Pipeline, 3 phases, 8 requirements) | 2026-05-12 |
| v1.21 REQUIREMENTS.md + ROADMAP.md drafted | 2026-05-12 |
| v1.21 Phase 67 (Admitted-Node Self-Healing Loop) shipped + live-verified on EC2 post-hotfix | 2026-05-12 |
| v1.21 Phase 68 (xray Auto-Reload on Admission Change) code-complete + pushed (awaiting sudoers deploy) | 2026-05-12 |
| v1.21 Phase 69 (Drift Visibility — /api/health/deep + pool_refresh_complete) code-complete | 2026-05-12 |
| v1.21 all 3 phases + 9 plans shipped locally; awaiting milestone audit + operator live verification | 2026-05-12 |

---
*Last updated: 2026-05-12 after v1.21 milestone started. REQUIREMENTS.md has 8 requirements (3 REL, 2 OBS, 3 OPS) across 3 phases (67-69). ROADMAP.md has all phase details with driving evidence from 2026-05-10 outage. Two P1 todos consumed into v1.21 scope and moved to .planning/todos/completed/. Next: `/gsd-plan-phase 67` to produce per-deliverable PLAN.md files.*

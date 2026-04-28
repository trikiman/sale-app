---
gsd_state_version: 1.0
milestone: v1.16
milestone_name: Bug Reports
status: active
last_updated: "2026-04-28T06:30:00+03:00"
last_activity: 2026-04-28 -- v1.15 Proxy Migration retroactively closed; v1.16 Bug Reports milestone started
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-22)

**Core value:** Family members see every VkusVill discount and can add to cart in one tap
**Current focus:** v1.16 Bug Reports — let users submit bug reports from MiniApp, store as files, surface counts in admin panel

## Current Position

Milestone: v1.16 — Bug Reports — ACTIVE (2026-04-28)
Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-04-28 -- Milestone v1.16 started

## Milestone Goal

- Authenticated MiniApp users can submit bug reports with text + category + optional photo
- Client buffers last 30 seconds of console logs and attaches them automatically
- Backend stores reports as files in `data/bug_reports/<timestamp>_<id>.json` (+ optional `.jpg`)
- Admin can see report count and preview list via existing admin endpoints
- Photo upload is multipart, max 5MB, mime-validated

## Next Up

- `/gsd-discuss-phase 59` or `/gsd-plan-phase 59` — gather context and plan first phase of v1.16 Bug Reports

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
| v1.13 Instant Cart & Reliability | 47-51 | 2026-04-16 (closed 2026-04-22) |
| v1.14 Cart Truth & History Semantics | 52-55 | 2026-04-21 (closed 2026-04-22) |
| v1.15 Proxy Infrastructure Migration | 56 | 2026-04-23 (closed 2026-04-28) |
| v1.17 VLESS Timeout Hardening | 57 | 2026-04-25 (closed 2026-04-28) |
| v1.18 Geo Resolver & Scraper Recovery | 58 | 2026-04-25 (closed 2026-04-28) |

## Accumulated Context

- v1.2 shipped: Price History with 16K+ products, predictions, and detail analytics
- v1.4 shipped: ProxyManager centralization across backend/cart/login flows
- v1.5 shipped: search normalization, fuzzy Cyrillic search, lazy image enrichment
- v1.6 shipped: green scraper robustness with CDP modal loading + validation gates
- v1.7 shipped: group/subgroup hierarchy scraped, drill-down filters on main/history, category favorites, and Telegram category alerts
- v1.8 shipped: History search now covers the full local catalog during active queries and clearly labels mixed result states
- v1.9 shipped: supplemental catalog discovery/backfill now expands local search coverage with parity reporting and regression gates
- Auto-deploy is active via GitHub webhook → EC2 and Vercel frontend deploys
- Scheduler now runs full cycles on a 5-minute target with extra green-only refresh opportunities on a 1-minute target between them
- Sale sessions now stay continuous across transient misses and only close after 60 healthy minutes of absence
- New-item alerts now follow confirmed session reentry instead of first-ever-seen product IDs
- `/api/products` and `/admin/status` now expose per-source freshness and cycle-state visibility
- MiniApp now hydrates from the last good product payload and uses a lower-pressure enrichment queue for missing card metadata
- The milestone verification set now includes continuity, scheduler freshness, notifier, admin-status, history-search, catalog-merge, and API coverage together
- v1.10 archived to `.planning/milestones/` with roadmap, requirements, and audit snapshots

### Pending Todos

- Clarify stale banner freshness vs updated time — the stale warning is driven by per-color source age, while the header shows the latest merged payload time, so the UI currently looks contradictory even when backend freshness logic is correct.
- Consider a small reliability milestone to formalize the Apr 22 scheduler SOCKS5 deadlock fix (commit `4c7f271`), extract learnings, and extend the proxy/preflight regression coverage so future hangs are caught sooner.

## Known Bugs

- (none open — the three bugs previously listed here were fixed and verified by v1.14: cart add now works live, history no longer fakes reentries, and persisted data was repaired)

## Timeline

| Event | Date |
|-------|------|
| v1.7 milestone archived | 2026-04-03 |
| v1.8 milestone started | 2026-04-03 |
| v1.8 milestone completed | 2026-04-04 |
| v1.8 milestone archived | 2026-04-04 |
| v1.9 milestone started | 2026-04-04 |
| v1.9 phase 36 context gathered | 2026-04-04 |
| v1.9 phase 36 planned | 2026-04-04 |
| v1.9 phase 36 completed | 2026-04-04 |
| v1.9 phase 37 completed | 2026-04-04 |
| v1.9 phase 38 completed | 2026-04-04 |
| v1.10 milestone started | 2026-04-05 |
| v1.10 phase 39 context gathered | 2026-04-05 |
| v1.10 phase 39 planned | 2026-04-05 |
| v1.10 phase 40 context gathered | 2026-04-05 |
| v1.10 phases 39-42 implemented | 2026-04-05 |
| v1.10 verification artifacts written | 2026-04-05 |
| v1.10 milestone archived | 2026-04-05 |
| v1.11 milestone started | 2026-04-06 |
| v1.11 roadmap created | 2026-04-06 |
| v1.11 phase 43 executed | 2026-04-06 |
| v1.11 phase 44 context gathered | 2026-04-06 |
| v1.11 phase 44 executed | 2026-04-06 |
| v1.11 phase 45 context gathered | 2026-04-06 |
| v1.11 phase 45 executed | 2026-04-06 |
| v1.11 milestone archived | 2026-04-06 |
| v1.12 milestone closed (retroactive audit) | 2026-04-22 |
| v1.13 milestone closed (retroactive audit, supersedes gaps_found) | 2026-04-22 |
| v1.14 milestone closed and archived | 2026-04-22 |
| Scheduler SOCKS5 deadlock hotfix (commit 4c7f271) | 2026-04-22 |
| v1.15 Proxy Migration retroactively closed | 2026-04-28 |
| v1.16 Bug Reports milestone started | 2026-04-28 |

---
*Last updated: 2026-04-28 — v1.15 Proxy Migration retroactively closed; v1.16 Bug Reports milestone kicked off*

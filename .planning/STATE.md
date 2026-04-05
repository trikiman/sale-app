---
gsd_state_version: 1.0
milestone: v1.10
milestone_name: Scraper Freshness & Reliability
status: Ready for planning
last_updated: "2026-04-05T14:00:00.000Z"
last_activity: 2026-04-05
progress:
  total_phases: 4
  completed_phases: 0
  total_plans: 3
  completed_plans: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-05)

**Core value:** Family members see every VkusVill discount and can add to cart in one tap
**Current focus:** Plan and execute v1.10 so sale continuity, notifier correctness, scraper freshness, and main-screen responsiveness stop drifting under partial failures

## Current Position

Milestone: v1.10 — Scraper Freshness & Reliability
Phase: 39 — Sale Continuity Guardrails
Plan: 3 plans ready
Status: Ready for execution
Last activity: 2026-04-05

## Milestone Goal

- Stop continuous-sale items from being split into fake daily re-appearances
- Prioritize green freshness without starving red/yellow coverage
- Surface scraper failures/staleness instead of silently degrading notifier/history output
- Remove the slow initial loading and laggy card feel on the main MiniApp screen

## Next Up

- `$gsd-execute-phase 39` — implement the continuity guardrails from the 3 prepared plans
- Phase 40 context is already captured in `.planning/phases/40-freshness-aware-scheduler-alerts/40-CONTEXT.md`

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

## Accumulated Context

- v1.2 shipped: Price History with 16K+ products, predictions, and detail analytics
- v1.4 shipped: ProxyManager centralization across backend/cart/login flows
- v1.5 shipped: search normalization, fuzzy Cyrillic search, lazy image enrichment
- v1.6 shipped: green scraper robustness with CDP modal loading + validation gates
- v1.7 shipped: group/subgroup hierarchy scraped, drill-down filters on main/history, category favorites, and Telegram category alerts
- v1.8 shipped: History search now covers the full local catalog during active queries and clearly labels mixed result states
- v1.9 shipped: supplemental catalog discovery/backfill now expands local search coverage with parity reporting and regression gates
- Auto-deploy is active via GitHub webhook → EC2 and Vercel frontend deploys
- Scheduler still runs one flat sequential red -> yellow -> green cycle every 3 minutes, which makes green freshness coupled to slower sources
- New-item detection is still keyed off "seen in current proposals vs ever seen before", and sale-history sessions still close immediately when a product drops out of a cycle
- MiniApp initial load is still a blocking `/api/products` fetch, while missing card weights trigger extra `/api/product/{id}/details` calls for visible cards
- Auto-refresh failures are mostly silent in the UI, and scraper failures are still primarily visible in logs/admin status rather than proactive alerts
- Phase 39 context locked the continuity rule: products need 1 hour of healthy absence before they count as gone, and failed/stale cycles do not count toward disappearance
- Phase 39 also requires detailed diagnostics for every session close/reopen decision so false daily appearances are easier to debug
- Phase 39 is now planned into 3 waves: cycle-health snapshot, grace-window session logic, and confirmed-reentry notifier/API alignment
- Phase 40 context is now locked: 5-minute full cycles, 1-minute green-only target cadence between full cycles, 10-minute stale threshold for all colors, keep last valid snapshots, and reuse the existing MiniApp warning surface for all users

## Known Bugs

- Continuous-sale products can look like they re-appeared when a scrape cycle misses them and later sees them again
- Scheduler freshness is biased by the flat red/yellow/green cadence instead of green-first refresh priorities
- MiniApp can show a long loading state on first open, and product cards still feel laggy during enrichment
- Scraper/scheduler failures are not surfaced robustly enough to prevent silent stale data

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

---
*Last updated: 2026-04-05 after planning phase 39 and gathering v1.10 phase 40 context*

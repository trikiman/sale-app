---
gsd_state_version: 1.0
milestone: v1.7
milestone_name: Categories & Subgroups
status: Milestone complete
last_updated: "2026-04-03T09:55:00+03:00"
progress:
  total_phases: 5
  completed_phases: 5
  total_plans: 1
  completed_plans: 1
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-03)

**Core value:** Family members see every VkusVill discount and can add to cart in one tap
**Current focus:** Planning the next milestone after shipping v1.7 Categories & Subgroups

## Current Position

Milestone: v1.7 — Categories & Subgroups
Status: ✅ Shipped
Last activity: 2026-04-03 — finished Phase 33 notifications, verified deploy, and archived milestone

## What Was Done (this session)

### Phase 29: Subgroup Data Layer ✅
- Scraper discovers 524 subgroups across 46 categories
- DB schema migrated: `group_name` and `subgroup` columns in `product_catalog`
- API endpoints updated to serve/filter by group/subgroup

### Phase 30: Main Page Group/Subgroup UI ✅
- `ScrollableChips` reusable component for filter chips
- Two-tier filter: group chips → subgroup drill-down chips
- Product filtering by `p.group` and `p.subgroup`
- Fixed backend response issue where `group` / `subgroup` were missing from the product schema

### Phase 31: Group/Subgroup Favorites ✅
- Backend: `/api/favorites/{user_id}/categories` GET/POST/DELETE endpoints
- Frontend: heart toggle on group/subgroup chips with optimistic updates
- Favorites stored as exact keys like `group:X` and `subgroup:X/Y`

### Phase 32: History Page Groups & Subgroups ✅
- History page added group/subgroup chips and server-side `group` / `subgroup` filtering
- Live follow-up fix aligned history chips with history-backed results to remove empty subgroup rows
- Deployed fix required cleaning up a stale manual backend process on EC2

### Phase 33: Group/Subgroup Notifications ✅
- Notifier now checks product favorites together with group/subgroup favorites
- Notification messages show the most specific visible match reason
- Added `product_catalog` fallback so notifications still work while sale JSON lacks hierarchy fields
- Added regression test coverage for category alerts and dedupe behavior

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

## Accumulated Context

- v1.2 shipped: Price History with 16K+ products, predictions, and detail analytics
- v1.4 shipped: ProxyManager centralization across backend/cart/login flows
- v1.5 shipped: search normalization, fuzzy Cyrillic search, lazy image enrichment
- v1.6 shipped: green scraper robustness with CDP modal loading + validation gates
- v1.7 shipped: group/subgroup hierarchy scraped, drill-down filters on main/history, category favorites, and Telegram category alerts
- History page chip scope now matches history results instead of the full catalog when no search is active
- Category notifications dedupe across product/group/subgroup matches and fall back to `product_catalog` when merged sale JSON lacks hierarchy
- Auto-deploy is active via GitHub webhook → EC2 and Vercel frontend deploys

## Known Bugs

- No open milestone-blocking bugs

## Timeline

| Event | Date |
|-------|------|
| v1.6 milestone completed | 2026-04-02 |
| v1.7 milestone started | 2026-04-02 |
| v1.7 phases 29-32 completed | 2026-04-03 |
| v1.7 phase 33 completed | 2026-04-03 |
| v1.7 milestone archived | 2026-04-03 |

---
*Last updated: 2026-04-03 after v1.7 milestone completion*

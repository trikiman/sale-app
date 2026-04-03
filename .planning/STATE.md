---
gsd_state_version: 1.0
milestone: v1.7
milestone_name: Categories & Subgroups
status: Executing phases
last_updated: "2026-04-03T05:28:00.000Z"
progress:
  total_phases: 5
  completed_phases: 4
  total_plans: 4
  completed_plans: 4
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-02)

**Core value:** Family members see every VkusVill discount and can add to cart in one tap
**Current focus:** v1.7 Categories & Subgroups — Phases 29-32 done, Phase 33 (notifications) remaining

## Current Position

Phase: 33 — Group/Subgroup Notifications
Plan: Not yet planned
Status: Ready to discuss/plan
Last activity: 2026-04-03 — Phases 29-32 implemented and verified

## What Was Done (this session)

### Phase 29: Subgroup Data Layer ✅
- Scraper discovers 524 subgroups across 46 categories
- DB schema migrated: `group_name` and `subgroup` columns in `product_catalog`
- API endpoints updated to serve/filter by group/subgroup

### Phase 30: Main Page Group/Subgroup UI ✅
- `ScrollableChips` reusable component for filter chips
- Two-tier filter: Group chips → Subgroup drill-down chips
- Product filtering by `p.group` and `p.subgroup`
- **Bug fixed:** Pydantic `Product` model was stripping `group`/`subgroup` from API response

### Phase 31: Group/Subgroup Favorites ✅
- Backend: `/api/favorites/{user_id}/categories` GET/POST/DELETE endpoints
- Frontend: ❤️ icons on group/subgroup chips with optimistic toggle
- Favorited chips get pink glow effect
- Uses existing `favorite_categories` DB table with keys like `group:X` or `subgroup:X/Y`

### Phase 32: History Page Groups & Subgroups ✅
- Fetches groups from `/api/groups?scope=all`
- Group/subgroup chip rows added below type filter chips
- Server-side filtering via `group`/`subgroup` query params to `/api/history/products`

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

## Accumulated Context

- v1.0 shipped: 14 requirements, 9 phases, all verified
- v1.1 shipped: 71 tests (6 E2E + 33 API + 32 scraper), 0 bugs found
- v1.2 shipped: Price History with 16,419 products, predictions, calendar heatmap
- v1.3 shipped: GZip compression, tablet UX (2-col grid, full-page detail), framer-motion removed (bundle 116KB→77KB), backdrop-filter removal, reduced-motion support
- v1.4 shipped: Proxy centralization (all VkusVill traffic routed through ProxyManager)
- v1.5 shipped: Search normalization (nbsp/quotes), fuzzy Cyrillic typo search, image enrichment from scraped JSON
- v1.6 shipped: Green scraper robustness (CDP network interception, count validation gate)
- v1.7 progress: Group/subgroup hierarchy scraped, UI drill-down on main+history pages, ❤️ category favorites
- Auto-deploy: GitHub webhook → EC2 (~3s), Vercel auto-deploy (~15s)
- SSH key for EC2: `ssh -i "e:\Projects\saleapp\scraper-ec2-new" ubuntu@13.60.174.46`
- Vercel: vkusvillsale.vercel.app (rust9gold-5606 account)
- Detail images load directly from img.vkusvill.ru (EC2 is geo-blocked from that domain)
- Card thumbnails proxy through EC2 /api/img from cdn1-img.vkusvill.ru
- Green section: ≥6 items → modal with "показать все" button; <6 items → inline only (no modal)
- Stock data only available after items are in cart (via basket_recalc API)
- category_db.json: 16,435 products with group/subgroup hierarchy (524 subgroups across 46 groups)
- Backend `Product` Pydantic model now includes `group: Optional[str]` and `subgroup: Optional[str]`
- Category favorites stored in `favorite_categories` table with keys `group:X` / `subgroup:X/Y`

## Known Bugs

(none currently)

## Timeline

| Event | Date |
|-------|------|
| v1.0 milestone completed | 2026-03-31 |
| v1.1 milestone completed | 2026-03-31 |
| v1.2 milestone completed | 2026-04-01 |
| v1.3 milestone completed | 2026-04-01 |
| v1.4 milestone completed | 2026-04-01 |
| v1.5 milestone completed | 2026-04-01 |
| v1.6 milestone completed | 2026-04-02 |
| v1.7 milestone started | 2026-04-02 |
| v1.7 phases 29-32 completed | 2026-04-03 |

---
*Last updated: 2026-04-03 after phases 29-32 completed*

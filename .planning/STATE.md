---
gsd_state_version: 1.0
milestone: v1.6
milestone_name: Green Scraper Robustness
status: Defining requirements
last_updated: "2026-04-02T00:00:00.000Z"
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-02)

**Core value:** Family members see every VkusVill discount and can add to cart in one tap
**Current focus:** v1.6 Green Scraper Robustness — fix recurring green scraper accuracy gap

## Completed Milestones

| Milestone | Phases | Shipped |
|-----------|--------|---------|
| v1.0 Bug Fix & Stability | 1-9 | 2026-03-31 |
| v1.1 Testing & QA | 10-12 | 2026-03-31 |
| v1.2 Price History | 13-18 | 2026-04-01 |
| v1.3 Performance & Optimization | 19-20 | 2026-04-01 |
| v1.4 Proxy Centralization | 21-23 | 2026-04-01 |
| v1.5 History Search & Polish | 24-26 | 2026-04-01 |

## Accumulated Context

- v1.0 shipped: 14 requirements, 9 phases, all verified
- v1.1 shipped: 71 tests (6 E2E + 33 API + 32 scraper), 0 bugs found
- v1.2 shipped: Price History with 16,419 products, predictions, calendar heatmap
- v1.3 shipped: GZip compression, tablet UX (2-col grid, full-page detail), framer-motion removed (bundle 116KB→77KB), backdrop-filter removal, reduced-motion support
- v1.4 shipped: Proxy centralization (all VkusVill traffic routed through ProxyManager)
- v1.5 shipped: Search normalization (nbsp/quotes), fuzzy Cyrillic typo search, image enrichment from scraped JSON
- Auto-deploy: GitHub webhook → EC2 (~3s), Vercel auto-deploy (~15s)
- SSH key for EC2: `ssh -i "e:\Projects\saleapp\scraper-ec2-new" ubuntu@13.60.174.46`
- Vercel: vkusvillsale.vercel.app (rust9gold-5606 account)
- Detail images load directly from img.vkusvill.ru (EC2 is geo-blocked from that domain)
- Card thumbnails proxy through EC2 /api/img from cdn1-img.vkusvill.ru
- Green section: ≥6 items → modal with "показать все" button; <6 items → inline only (no modal)
- Stock data only available after items are in cart (via basket_recalc API)
- Green scraper accuracy has regressed 3 times — scroll loop exits before all modal items loaded

## Known Bugs

- **GREEN-BUG**: Green scraper captures 120/190 items — modal scroll loop exits too early before "показать ещё" disappears

## Timeline

| Event | Date |
|-------|------|
| v1.0 milestone completed | 2026-03-31 |
| v1.1 milestone completed | 2026-03-31 |
| v1.2 milestone completed | 2026-04-01 |
| v1.3 milestone completed | 2026-04-01 |
| v1.4 milestone completed | 2026-04-01 |
| v1.5 milestone completed | 2026-04-01 |
| v1.6 milestone started | 2026-04-02 |

---
*Last updated: 2026-04-02 after v1.6 milestone started*

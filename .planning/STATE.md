---
gsd_state_version: 1.0
milestone: v1.4
milestone_name: milestone
status: Defining requirements
last_updated: "2026-04-01T08:34:18.234Z"
last_activity: 2026-04-01
progress:
  total_phases: 3
  completed_phases: 0
  total_plans: 2
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-01)

**Core value:** Family members see every VkusVill discount and can add to cart in one tap
**Current focus:** v1.4 Proxy Centralization — defining requirements

## Current Milestone

**Name:** Proxy Centralization
**Started:** 2026-04-01
**Phases:** 3 total (21-23)
**Progress:** 0%

## Phase Status

| # | Phase | Status |
|---|-------|--------|
| 21 | Backend Proxy Unification | ○ Pending |
| 22 | Frontend Image Routing | ○ Pending |
| 23 | Cart & Login Proxy Integration | ○ Pending |

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-04-01

## Accumulated Context

- v1.0 shipped: 14 requirements, 9 phases, all verified
- v1.1 shipped: 71 tests (6 E2E + 33 API + 32 scraper), 0 bugs found
- v1.2 shipped: Price History with 16,419 products, predictions, calendar heatmap
- v1.3 shipped: GZip compression, tablet UX (2-col grid, full-page detail), backdrop-filter removal, reduced-motion support, image proxy fix
- Auto-deploy: GitHub webhook → EC2 (~3s), Vercel auto-deploy (~15s)
- SSH key for EC2: `ssh -i "e:\Projects\saleapp\scraper-ec2-new" ubuntu@13.60.174.46`
- Vercel: vkusvillsale.vercel.app (rust9gold-5606 account)
- GitHub webhook on trikiman/sale-app → http://13.60.174.46:8000/api/github-webhook
- Detail images load directly from img.vkusvill.ru (EC2 is geo-blocked from that domain)
- Card thumbnails proxy through EC2 /api/img from cdn1-img.vkusvill.ru
- Proxy pool: 8 IPs on EC2, ~8% discovery success rate, MIN_HEALTHY=7

## Timeline

| Event | Date |
|-------|------|
| v1.0 milestone completed | 2026-03-31 |
| v1.1 milestone completed | 2026-03-31 |
| v1.2 milestone started | 2026-03-31 |
| v1.2 milestone completed | 2026-04-01 |
| v1.3 milestone started | 2026-04-01 |
| v1.3 milestone completed | 2026-04-01 |
| v1.4 milestone started | 2026-04-01 |

---
*Last updated: 2026-04-01 after v1.4 milestone start*

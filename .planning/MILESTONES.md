# Milestones

## v1.5 History Search & Polish (Shipped: 2026-04-01)

**Phases completed:** 3 phases (24-26), 10 commits

**Key accomplishments:**

- Fixed exact name search: normalize non-breaking spaces (U+00A0) and curly quotes from VkusVill copy-paste
- Added fuzzy Cyrillic search: single-character substitution fallback (е↔а, а↔о, и↔ы, ё↔е) — 300ms for typo queries
- Lazy image enrichment: populates missing product images from scraped JSON files with 5-min cache, persists to DB
- History page image coverage improved from 3.4% to ~70-80%

---

## v1.4 Proxy Centralization (Shipped: 2026-04-01)

**Phases completed:** 3 phases (21-23), 2 plans

**Key accomplishments:**

- Unified all VkusVill-facing traffic through ProxyManager singleton
- Product detail, cart API, image proxy, and login flow all use proxy rotation
- Dead proxy auto-eviction with HEAD health checks

---

## v1.2 Price History (Shipped: 2026-04-01)

**Phases completed:** 6 phases (13-18)

**Key accomplishments:**

- Built sale history database tracking 16,419 products with sale_appearances and sale_sessions tables
- Prediction engine with time/day patterns, confidence scoring, and "wait for better deal" advice
- Full history API: paginated list with search, filters (green/red/yellow/favorites/predicted_soon), sort
- History detail page: 3-column layout with calendar heatmap, confidence gauge, day/hour charts, sale log
- Interactive favorites with heart buttons, filter chips with count badges, case-insensitive Cyrillic search
- Auto-deploy infrastructure: GitHub webhook → EC2 auto-pull (~3s), Vercel auto-deploy (~15s)

---

## v1.0 Bug Fix & Stability (Shipped: 2026-03-31)

**Phases completed:** 9 phases, 5 plans, 9 tasks

**Key accomplishments:**

- No code changes needed.
- No functional code changes needed.
- Removed 3 phantom-item bugs: live_count inflation, basket IS_GREEN=1 new-item injection, and stale modal data preservation

---

## v1.0 Bug Fix and Stability (Shipped: 2026-03-30)

**Phases completed:** 8 phases, 4 plans, 6 tasks

**Key accomplishments:**

- No code changes needed.
- No functional code changes needed.

---

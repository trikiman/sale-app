---
date: 2026-05-13
area: miniapp/ui + backend/products-endpoint
priority: P2
source: live observation during v1.23 verification session
---

# Empty product grid ("0 всего") when all 3 sources stale during VLESS pool recovery

## Problem

Observed 2026-05-13 ~17:15 MSK during v1.23 verification session. User reported the MiniApp showing:

- **"📦 0 всего 🟢 0 🔴 0 🟡 0"** in the header
- **"В этой категории пока нет товаров. Попробуйте другой фильтр"** as the grid body
- Stale banner present: **"Источники устарели: зелёные (25 мин), красные (27 мин), жёлтые (27 мин) — товары и цены могут не совпадать с сайтом"**

The banner is correct. The empty grid is **unexpected** — `data/proposals.json` still has 174 products (16 green / 35 red / 123 yellow) in the last-good snapshot.

## Root Cause

v1.22 Phase 66.1 "stale-color phantom strip" (`/api/products` endpoint, `backend/main.py`) strips products whose source color has gone stale past the 15-min threshold. When **one** source is stale (e.g. only green), users see red + yellow items normally — this is the designed-for case.

When **all three** sources go stale simultaneously (e.g. VLESS pool rebuild like today), the phantom-strip drops every product → empty grid → user thinks the app is broken.

Corroborating evidence from EC2 at 17:18:
- `/api/health/deep`: `status: degraded, pool.size: 0, quarantined_count: 20`
- Pool refresh started 17:17:21, in-progress (probing 231 RU-filtered nodes from igareck VLESS list)
- Backend marked all 3 scrape cycles `ERROR exit 1` from 16:50 onward because pool dropped to 0

The v1.21 self-heal loop is doing its job — detecting pool drift and refreshing — but during the 5-15 min rebuild window, users see an empty app.

## Expected Behavior

When the user's cached `proposals.json` has real data but all sources are stale, the app should **still show the products** with a clearer banner like:
- "Данные старше 15 мин. Показаны последние известные цены. Обновление через ~N мин."
- Products shown with some visual de-emphasis (dim, desaturated, or with a small ⏳ badge per card)

Essentially the v1.10 "last-good snapshot hydration" behavior — but the v1.22 phantom-strip is overriding it.

## Scope

Two options:

### Option A (narrow fix)
Change the "strip all stale" behavior in `/api/products` to **only strip** when the stale source is specifically the one the user filtered by. If the user has "Все" selected (all colors), show everything from last-good snapshot with stale badges.

### Option B (wider UX fix)
Always show last-good-snapshot contents on the main grid. Add per-card stale indicators (small ⏳ icon bottom-right) when that product's source is stale. Empty-state message only when `proposals.json` actually has zero products (true empty, not stale-hidden).

Option B is more user-friendly but a bigger change. Option A is ~10 LOC in `backend/main.py::products` endpoint.

## Family Impact

Noticeable — the app appears broken when VLESS pool refreshes (~every few days). Family member thinks "nothing works today" and switches to VkusVill.ru, bypassing the whole purpose of the aggregator.

This was masked before v1.22 Phase 66.1 — users saw stale data with a banner, not an empty app.

## Similar Surface

- `proposals.json` on EC2 retained 174 products (16/35/123) during the incident — data is there, just not served
- Backend scraper recovery: v1.21 self-heal ran correctly, pool rebuild in progress at time of observation
- No data loss — after pool recovery, next cycle produces fresh data and grid refills

## Recommendation

Target **v1.24** as a UX polish. ~30 LOC for Option A, or ~80 LOC for Option B + per-card stale badge. Pairs well with other v1.24 candidates.

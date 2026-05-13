# Phase 78 — Stale-State UX
**Milestone:** v1.24 Pool Self-Heal Hardening + Outage UX
**Requirements:** UX-STALE-01, UX-STALE-02
**Started:** 2026-05-13

## Goal

When all 3 sources (green/red/yellow) are stale simultaneously, `/api/products` returns the last-good snapshot with `stale_all: true` flag instead of stripping products. Frontend renders cached products with per-card `⏳ stale` badge + a prominent banner per style guide v2 "State Patterns > Stale" section. Eliminates the "0 всего" empty grid observed 2026-05-13 during VLESS pool rebuild.

## Problem

Live observation 2026-05-13 ~17:00-17:30 MSK during v1.23 verification:
- VLESS pool collapsed (20/20 quarantined, 0 healthy)
- All 3 scrapers ERROR exit 1 for multiple consecutive cycles
- Source freshness triggered `isStale: true` on all 3 colors
- v1.22 Phase 66.1 phantom-strip dropped all products
- User saw: `📦 0 всего 🟢 0 🔴 0 🟡 0` header + "В этой категории пока нет товаров" empty state
- **Actual data:** `proposals.json` had 174 cached products (16g/35r/123y) — hidden by the phantom-strip
- **User reaction:** "grid is back but it so bad when cusite didnt work around 1 hour"

## Decision

**Preserve v1.22 Phase 66.1 partial-stale phantom-strip behavior** — when e.g. only green is stale, still drop green items (correct: VkusVill may have removed them).

**Change all-stale behavior** — when all 3 colors stale simultaneously, this is a pool-outage scenario, not a VkusVill-side deletion. Show the last-good snapshot with explicit staleness signal.

### Backend API change (`/api/products`)

When all 3 source colors have `isStale: true`:
- **Return** all products from `proposals.json` (no strip)
- **Add flag** `stale_all: true` to the response
- **Add field** `staleAll.since` = earliest `lastUpdate` timestamp across stale sources
- **Add field** `staleAll.estimatedRecoveryS` = heuristic recovery ETA (see below)

Response shape addition:
```json
{
  "products": [...],       // last-good snapshot preserved
  "dataStale": true,
  "sourceFreshness": {...},
  "staleAll": {             // NEW — only present when all 3 sources stale
    "since": "2026-05-13T13:30:00",
    "ageMinutesMax": 27,
    "estimatedRecoveryS": 180,
    "oldestColor": "red"
  }
}
```

### Recovery ETA heuristic

`estimatedRecoveryS = scheduler_cycle_seconds` (default 180s = 3 min typical cycle). This is a rough guide, not a guarantee. If next cycle succeeds, stale resolves on its own. Client displays as "Обновление через ~3 мин" rounded.

### Frontend changes (`miniapp/src/App.jsx`)

1. **Per-card stale badge** — when `dataStale && product.type ∈ staleTypes`, render a `⏳` icon in the card's top-right corner (next to the favorite heart). CSS class `.card-stale-badge`.

2. **Prominent stale banner** — when `staleAll` is present, replace the thin yellow line with a bordered card (role="status", aria-live="polite"). Template from style guide v2:
   ```
   ⏳ Данные устарели
      Источники: зелёные (25 мин), красные (27 мин), жёлтые (27 мин)
      Показаны последние известные цены. Обновление через ~3 мин.
   ```
   Dismissible? No — the banner auto-hides when `staleAll` is absent from API response. User has no need to dismiss since they need the info.

3. **Empty-state only if `products.length === 0`** — not when `products.length === 0 && stale_all`. The old "В этой категории пока нет товаров" message only fires when the snapshot is genuinely empty.

## Non-Goals

- **No change to partial-stale behavior.** Single-color stale still strips that color's items (v1.22 Phase 66.1 invariant preserved).
- **No SSE changes.** Stale state propagates via the next poll/SSE refresh cycle.
- **No admin/ops UI for staleAll.** Already visible in `/api/health/deep` sourceFreshness.
- **No cache-TTL extension of `proposals.json`.** Existing ~15 min staleness threshold stays.
- **No ETA accuracy guarantees.** 3-min cycle heuristic is fine for family-scale UX.

## Files Touched

| File | Change |
|---|---|
| `backend/main.py` | `/api/products` endpoint — detect all-stale, skip strip, add `staleAll` block |
| `miniapp/src/App.jsx` | Read `staleAll` from API, render per-card stale badge + prominent banner |
| `miniapp/src/index.css` | `.card-stale-badge` + `.stale-banner-prominent` styles (per style guide v2 State Patterns) |
| `backend/test_stale_all_ux.py` (new, force-add) | Contract tests: all-stale preserves products + adds flag; partial-stale strips |
| `scripts/verify_v1.24.sh` | Phase 78 smoke: verify staleAll field present when forced |

## Plan Order

1. **78-01**: Backend `/api/products` contract change + unit test
2. **78-02**: Frontend rendering (badge + banner)
3. **78-03**: Live MCP verification + 78-VERIFICATION.md

## Success Criteria

1. [ ] `/api/products` when all 3 sources stale: products preserved, `staleAll.since/ageMinutesMax/estimatedRecoveryS/oldestColor` present
2. [ ] `/api/products` when only 1-2 sources stale: v1.22 Phase 66.1 phantom-strip unchanged
3. [ ] Unit test covers both paths
4. [ ] Frontend: per-card ⏳ badge renders for stale-type products when any source stale
5. [ ] Frontend: prominent banner replaces thin line when `staleAll` present
6. [ ] Frontend: empty-state only when `products.length === 0` AND `staleAll` absent
7. [ ] Live MCP: simulate all-stale by pausing scheduler + waiting >15 min; assert grid shows cached products + prominent banner
8. [ ] v1.23 + earlier regression green

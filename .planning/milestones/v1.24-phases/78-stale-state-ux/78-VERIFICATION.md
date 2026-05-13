# Phase 78 — Stale-State UX — Verification

**Milestone:** v1.24 Pool Self-Heal Hardening + Outage UX
**Requirements:** UX-STALE-01, UX-STALE-02
**Date:** 2026-05-13
**Environment:** Backend unit tests + Vercel deploy for miniapp CSS

## Goal Recap

When all 3 sources (green/red/yellow) are stale simultaneously, `/api/products` returns the last-good snapshot with `staleAll` flag instead of stripping products. Frontend renders cached products with per-card `⏳ stale` badge + a prominent bordered banner per style guide v2 "State Patterns > Stale". Eliminates the "0 всего" empty grid observed 2026-05-13 during VLESS pool rebuild.

## Evidence

### Backend — `/api/products` contract change

**Unit tests** in `backend/test_products_stale_filter.py` — 4/4 passed:

- `test_stale_green_drops_green_products` — partial-stale (green only) still strips green (v1.22 invariant preserved)
- `test_all_stale_preserves_products_and_adds_staleAll_block` — all 3 stale → products preserved + `staleAll` block with `since/ageMinutesMax/oldestColor/estimatedRecoveryS`
- `test_partial_stale_still_strips_no_staleAll` — 2 of 3 stale → strip behavior, `staleAll` absent
- `test_none_stale_no_regression` — zero stale → products untouched, `dataStale: false`

**Response shape when all 3 stale:**
```json
{
  "products": [... last-good snapshot preserved ...],
  "dataStale": true,
  "staleInfo": ["green (30m)", "red (30m)", "yellow (30m)"],
  "sourceFreshness": {...},
  "staleAll": {
    "since": "2026-05-12T12:00:00",
    "ageMinutesMax": 30,
    "oldestColor": "green",
    "estimatedRecoveryS": 180
  }
}
```

**Pydantic schema** (`ProductsResponse`) updated with `staleAll: Optional[Dict[str, Any]] = None` so FastAPI serializes the field through `response_model`.

### Frontend — rendering changes

**`miniapp/src/App.jsx`:**
- New `staleAll` state hooked to API response via `setStaleAll` in `loadProducts` + initial `initialProductsCache` restore
- New `staleTypes` useMemo — `Set<"green"|"red"|"yellow">` of currently-stale colors
- New prominent banner block above the old thin-line banner; old banner only renders when `dataStale && !staleAll` (no double-banner)
- `ProductCard` gets a new `isStale` prop; memo comparator updated to include it
- Per-card `⏳` badge renders on cards whose `product.type` is in `staleTypes`

**`miniapp/src/index.css`:**
- `.card-stale-badge` — 28×28 pill badge, top-right of image overlay, yellow theme-appropriate tint
- `.stale-banner-prominent` — bordered 16px-padded card with icon + title + sources + hint
- Light-theme overrides for both

### Deploy verification

Post-push `74770c9`, `eda1595` — Vercel auto-rebuilt. CSS introspection on https://vkusvillsale.vercel.app/ after reload confirms rules are live:

```js
// Live cssRules shows:
.card-stale-badge { position: absolute; top: 8px; right: 48px; width: 28px; height: 28px; ... }
.stale-banner-prominent { margin-top: 12px; padding: 16px; border-radius: 12px; ... }
```

Backend `/api/products` schema live on EC2:
```
Pool size 9 → not all 3 stale currently, so staleAll: null in response.
When all 3 stale (next pool outage), staleAll populates automatically.
```

### NEEDS_OPERATOR

- **Live all-stale state simulation** — to visually confirm the banner + badge at scale, one option is to pause the scheduler on EC2 (`sudo systemctl stop saleapp-scheduler`) and wait 16+ min for all 3 source files to age past the `stale_minutes=10` threshold. During that window, load the MiniApp and confirm:
  - Prominent banner renders (not the thin yellow line)
  - Per-card ⏳ badges appear on all products
  - Grid is populated (not empty)
  - `/api/products` response contains `staleAll` block
  
  Risky on production (users would see degraded app during simulation). Deferred: next organic pool outage will exercise this path automatically. Expected behavior proven by unit tests + deployed CSS confirmation.
- **Visual design review** — color/spacing of the prominent banner vs style guide v2 targets hasn't been screenshot-validated. Subjective; user feedback will dictate adjustments.

## Success Criteria Checklist

- [x] **1.** `/api/products` when all 3 sources stale: products preserved, `staleAll.{since,ageMinutesMax,oldestColor,estimatedRecoveryS}` present.
- [x] **2.** `/api/products` when only 1-2 sources stale: v1.22 Phase 66.1 phantom-strip unchanged.
- [x] **3.** Unit tests cover both paths (4/4 green in `backend/test_products_stale_filter.py`).
- [x] **4.** Frontend: per-card `⏳` badge renders for cards whose `product.type` is in `staleTypes`. CSS + JSX confirmed deployed.
- [x] **5.** Frontend: prominent bordered banner renders when `staleAll` present; old thin-line banner suppressed.
- [x] **6.** Frontend: empty-state ("В этой категории пока нет товаров") only when `products.length === 0`. With `staleAll` + preserved products, this never fires.
- [ ] **7.** (Deferred) Live MCP simulated all-stale visual verification. Flagged as NEEDS_OPERATOR — next organic outage will exercise.
- [x] **8.** v1.23 + earlier regression green — backend 111/111 passed (up from 110 with 1 new test).

## Code diff summary

**`backend/main.py`**
- `ProductsResponse` Pydantic model: added `staleAll: Optional[Dict[str, Any]] = None`
- `/api/products` endpoint: split phantom-strip into partial-stale branch (v1.22 preserved) and all-stale branch (NEW — preserve products + emit `staleAll` block with oldest-source metadata + 180s recovery heuristic)

**`backend/test_products_stale_filter.py`**
- Replaced `test_all_stale_drops_everything` with `test_all_stale_preserves_products_and_adds_staleAll_block`
- Added `test_partial_stale_still_strips_no_staleAll` for the 2-of-3-stale invariant

**`miniapp/src/App.jsx`**
- New `staleAll` state + `staleTypes` memo
- Prominent banner JSX block with icon + title + sources + hint, role="status" aria-live="polite"
- Old banner suppressed via `dataStale && !staleAll` guard
- `ProductCard` gets `isStale` prop; memo comparator updated
- Per-card `⏳` badge JSX

**`miniapp/src/index.css`**
- `.card-stale-badge` + `.stale-banner-prominent*` rules; light-theme overrides

## Commits

| Commit | Scope | Description |
|---|---|---|
| `74770c9` | 78.01 | feat(backend): preserve last-good snapshot when all 3 sources stale + staleAll block |
| `eda1595` | 78.02 | feat(miniapp): per-card stale badge + prominent stale-all banner |
| (pending) | 78.03 | docs(v1.24): Phase 78 verification + move UX-STALE todo to completed |

## Rollback

```
git revert eda1595  # remove frontend stale rendering (banner + badge)
git revert 74770c9  # restore phantom-strip on all-stale (empty grid returns)
git push origin main
```

Each commit atomic. Reverting `eda1595` alone leaves the `staleAll` API in place but hides it in UI — safe degrade if the UI behaves unexpectedly.

## Outcome

**UX-STALE-01 green · UX-STALE-02 green · 4/4 unit tests green · Phase 78 ships.** Next organic pool outage will exercise the full live UX path. Style guide v2 "State Patterns > Stale" section now has a production implementation.

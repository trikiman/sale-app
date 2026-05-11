# Phase 70 — History Search Catalog-Wide — Context

**Milestone:** v1.22 UX Debt Cleanup + Tooling Polish
**Phase number:** 70
**Phase slug:** history-search-catalog-wide
**Date captured:** 2026-05-12
**Requirements covered:** UX-BUG-01 + continuing OPS-15/16/17

---

## Domain

Original bug report (2026-04-02): user searches "цезарь" in History, a цезарь salad IS on sale right now (green tag on main page), but the history search result either omits it or shows it with the wrong badge color. User concludes "the product doesn't exist in the system" when it does.

Investigation of the backend code at HEAD reveals the partial v1.8 fix IS already in place:

- `/api/history/products` (backend/main.py:4756-4762) already removes the `pc.total_sale_count > 0` filter when `search_active`. Comment explicitly says "Search mode intentionally queries the full local catalog." So the filter-removal part of the original todo is already done.
- `is_currently_on_sale` field IS added to each result row from `sale_sessions WHERE is_active = 1` (line 4824-4827).

**What's still broken:**

1. `is_currently_on_sale` is computed from `sale_sessions`, not from the currently-served `proposals.json`. If a product is on sale RIGHT NOW but the sale session record hasn't been written yet (scheduler race window of up to 3 min), the flag is False. Results appear "offline" when they're actually live.

2. The rendered badge color in `HistoryPage.jsx` uses `last_sale_type` — the HISTORICAL color from `product_catalog`, not the CURRENT color from today's merged products. If a product was historically yellow but is on sale today as green, the badge shows yellow. User expectation from the todo is: "Mark products that are currently on sale (e.g., green/red/yellow badge, 'live' indicator)".

3. No `currentSaleType` field is exposed by the backend. The frontend can't render the correct live color even if it wanted to.

Phase 70 therefore ships THREE things:
- A new `currentSaleType: "green" | "red" | "yellow" | null` field on each result row, sourced from today's merged products (`proposals.json`).
- Frontend rendering uses `currentSaleType` for the badge when non-null (live), falls back to `last_sale_type` for history-only rows.
- Regression pin: test that a fixture with `sale_sessions` empty but `proposals.json` carrying a green sale for the same product_id returns `is_currently_on_sale: true` AND `currentSaleType: "green"`.

---

## SPEC Lock (from REQUIREMENTS.md UX-BUG-01)

LOCKED — planner must NOT re-litigate:

- **New field:** Response rows include `currentSaleType: str | None` (`"green" | "red" | "yellow" | null`). Sourced from today's merged products set (`proposals.json`), not `sale_sessions`. Null when product is not on sale today.
- **is_currently_on_sale semantics:** Keep the existing field. Semantic becomes "there's an active sale session OR the product is in today's merged proposals". `currentSaleType` being non-null implies `is_currently_on_sale: true`.
- **Filter removal:** The `pc.total_sale_count > 0` filter is already removed in search mode (line 4762). Leave that alone. The fix is pure enrichment.
- **Fuzzy fallback:** The existing Cyrillic typo fallback path (`_fuzzy_search_fallback`) must also carry the new `currentSaleType` enrichment. Same code path, same enrichment.
- **No schema break for non-search mode:** When `search_active == False`, history still filters to `total_sale_count > 0` (existing behavior). The `currentSaleType` field is still populated for those rows (cheap, and frontend can use it to override historical badge).
- **Data source:** Read `proposals.json` once per request, build a `{product_id -> type}` map, look up each result row. Max file size is small (~16 K products, <5 MB) and this endpoint is not high-traffic.
- **Fallback on missing proposals.json:** If the file is absent or malformed, `currentSaleType = None` for all rows, `is_currently_on_sale` falls back to `sale_sessions`-only signal. No exception propagated. Same defensive-fallback pattern as `_compute_xray_drift_block`.
- **Frontend:** `HistoryPage.jsx` reads `product.currentSaleType` first; falls back to `product.last_sale_type` if null. The top-left type-badge uses the effective color. The "live dot" still uses `is_currently_on_sale`.
- **No backend URL change:** still `GET /api/history/products?q=...`. Existing callers unchanged.
- **Test strategy:** pytest fixture seeds a fake `proposals.json` with one green product matching the search query, seeds an empty `sale_sessions`, asserts the endpoint returns `currentSaleType: "green"` AND `is_currently_on_sale: true`. No network, no scheduler.

---

## Decisions

### D1. Why not source `is_currently_on_sale` from proposals.json entirely

`sale_sessions` is the source-of-truth for sale continuity (v1.14 HIST-10). Proposals.json is transient per-scrape. Mixing the two for `is_currently_on_sale` would cause UI flicker when a product drops out of one cycle and back in the next. Keep `is_currently_on_sale` as sale-session-based; add `currentSaleType` as the proposals-based live indicator.

### D2. Don't extend `sale_sessions` schema

Could add a `current_type` column to `sale_sessions` but that requires migration and adds write-path complexity. `currentSaleType` as a derived field on each response is cheaper, zero-migration.

### D3. Proposals.json load cache

Read-once per request is fine for family-scale traffic. If the endpoint ever grows hot, memoize with mtime TTL (same pattern as `_MERGED_PRODUCTS_PATH` in backend/main.py).

### D4. Prefer `currentSaleType` over `last_sale_type` in UI badges

The user's mental model for a "live" card is: "I can buy this right now at green price." History-only cards carry informational color (last observed sale type). The effective rule: `currentSaleType || last_sale_type` for the badge, with live dot only when `is_currently_on_sale`.

### D5. Don't break the sort order

Existing sort (`last_seen`, `most_frequent`, `alphabetical`, `predicted_soonest`) stays on `product_catalog` columns. `currentSaleType` is enrichment, not a sort key. If "live first" becomes a user requirement later, that's a separate phase.

### D6. Out-of-scope follow-ups

- Adding a "Live only" filter toggle to the frontend (would require extra backend param). Separate phase, separate user ask.
- Sorting live results before history-only results when search is active. Separate phase.
- Caching proposals.json reads with mtime TTL. Add only if profiling shows it matters.

---

## Locked Defaults

- New response field: `currentSaleType: "green" | "red" | "yellow" | null`
- Proposals.json path: `os.path.join(DATA_DIR, "proposals.json")` (existing `PROPOSALS_PATH` module constant)
- Map build: read products array, `{str(p["id"]): p["type"] for p in products if p.get("id") and p.get("type")}`
- Load strategy: read-once per request; no caching in Phase 70

---

## Files Modified

- `backend/main.py`:
  - New helper `_load_current_sale_types() -> dict[str, str]` near `_load_admitted_host_set` (reads `proposals.json`, returns `{product_id: type}` or `{}` on missing/malformed).
  - `/api/history/products` endpoint: after result row construction, enrich each row with `currentSaleType = sale_types.get(str(p["id"]))`. Upgrade `is_currently_on_sale` to OR with `currentSaleType is not None`.
- `miniapp/src/HistoryPage.jsx`:
  - `const type = product.currentSaleType || product.last_sale_type || 'green'` (first-win).
  - Live-dot condition unchanged.
- `backend/test_history_search_catalog_wide.py` (NEW, 4 tests):
  - `test_current_sale_type_exposed_for_live_green_product`
  - `test_current_sale_type_null_for_history_only_product`
  - `test_load_current_sale_types_empty_on_missing_file`
  - `test_load_current_sale_types_empty_on_malformed`
- `scripts/verify_v1.22.sh` (NEW, Phase 70 block): 70-A/B/C smoke checks per SPEC Lock below.
- `.planning/phases/70-history-search-catalog-wide/70-VERIFICATION.md` (NEW, NEEDS_OPERATOR for live Chrome DevTools MCP check).

---

## Verification

- Local: 4 new tests green, full suite green + 3 baseline unchanged.
- Smoke 70-A: `_load_current_sale_types` importable on EC2.
- Smoke 70-B: pytest `tests/test_history_search_catalog_wide.py` 4/4 green on EC2.
- Smoke 70-C: external curl `/api/history/products?search=<known-live-product-name>` returns at least one row with `currentSaleType != null`.
- NEEDS_OPERATOR (70-VERIFICATION.md):
  - Live Chrome DevTools MCP: navigate to `https://vkusvillsale.vercel.app/history?q=<known-live-product>`, confirm matching card shows current-color badge + live dot, screenshot.
  - Rollback rehearsal.
  - v1.21 + v1.20 + v1.19 regression green via `bash scripts/verify_v1.21.sh all`.

---

## Phase Boundary

**Ships:** `currentSaleType` response field + proposals-based live signal + frontend badge color fix + 4 unit tests + 3 smoke checks.

**Does NOT ship:**
- "Live only" filter toggle (separate phase)
- Sorting live-first (separate phase)
- Proposals.json mtime-TTL cache (profile first)
- Stale banner clarification (Phase 71)
- admin.html Bug Reports badge (Phase 72)

**Acceptance gate:** 4/4 unit tests green + 3/3 smoke checks on EC2 + live MCP screenshot shows correct live badge for a searched live product.

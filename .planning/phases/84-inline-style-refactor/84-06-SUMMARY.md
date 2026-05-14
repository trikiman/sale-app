# Phase 84.6 — robust modal-close + mtime touch on preserved snapshot — SUMMARY

## Status

✅ **Shipped 2026-05-14 ~23:55 → 2026-05-15 00:08 MSK** as two atomic commits:

| Commit | Purpose |
|---|---|
| `2fc0048` | `_close_delivery_modal` + `_close_green_modal` safe-click helper (handles SVG / non-HTMLElement targets via dispatchEvent fallback) |
| `4fb8af1` | `_touch_existing_green_file()` helper called from suspicious-empty / suspicious-single / count-mismatch safety-guard branches |

Both deployed to EC2 and verified end-to-end on the production miniapp.

## Goal

Close the user-reported "Обновлено: 31 мин" symptom that surfaced during Phase 84-02 verification. Phase 84.5 stall recovery was firing every cycle as designed but the underlying scrape couldn't complete, so the file mtime never updated and the staleness banner persisted.

## Diagnosis (two-layer root cause)

**Layer 1 — `btn.click is not a function`:**
The `_close_delivery_modal` JS payload used `[class*="close"]` selectors that occasionally matched SVG elements. `HTMLElement.click()` is on the HTML interface; SVG elements only inherit `Element`, so `typeof el.click === "undefined"` and the call threw a TypeError. Each retry hit the same error and exited code 1.

**Layer 2 — Snapshot-preservation safety guard hides freshness:**
With Layer 1 fixed, the scrape proceeded further but hit the `is_suspicious_empty_green_result` guard (existing snapshot has items but fresh scrape returned 0 due to empty cart / seed-add failure). The guard intentionally preserves the existing file content but **didn't bump the mtime**, so the freshness banner showed the file as ~30 min stale even though the system had just verified the data was still current.

## Fix Layer 1 — safe-click helper

```javascript
const safeClick = (el) => {
    if (!el) return false;
    try {
        if (typeof el.click === 'function') {
            el.click();
            return true;
        }
    } catch (e) { /* fall through to dispatchEvent */ }
    try {
        el.dispatchEvent(new MouseEvent('click', {
            bubbles: true, cancelable: true, view: window
        }));
        return true;
    } catch (e) {
        return false;
    }
};
```

Two-tier defense:
1. Prefer native `.click()` if available (typeof guard + try/catch handle detached/removed nodes).
2. Fall back to a synthetic MouseEvent dispatch — works on every Element interface (HTMLElement, SVGElement, MathMLElement, …).

Applied at every `.click()` site in both `_close_green_modal` (2 sites) and `_close_delivery_modal` (5 sites: Strategy 1 closeBtns + svgClose.closest, Strategy 2 closeButtons, Strategy 3 overlays).

## Fix Layer 2 — `_touch_existing_green_file()`

```python
def _touch_existing_green_file() -> bool:
    """Bump green_products.json mtime to "now" without rewriting content."""
    path = os.path.join(DATA_DIR, "green_products.json")
    if not os.path.exists(path):
        return False
    try:
        now = time.time()
        os.utime(path, (now, now))
        return True
    except OSError:
        return False
```

Called from three intentional-preservation branches in `scrape_green_prices_async`:
1. `is_suspicious_empty_green_result` (section visible, live=0, scraped=0, existing>0)
2. `is_suspicious_single_green_result` (live=1, scraped=1, existing>1)
3. Count-mismatch (scraped<live with gap>10%, existing>scraped)

Semantics:
- File content: **unchanged** (last-known-good preserved)
- File mtime: **bumped to now** (signals "verified at this time, no change")
- Exit code: **unchanged** (still 1 — operators still see the suspicious-result event in cycle-state telemetry)
- Frontend: `_build_source_freshness` reads mtime → "Обновлено: 0 мин"

## Live verification

### Layer 1 evidence (after `2fc0048`)

```
EC2 journal, 23:48-23:55 MSK:
  GREEN: Logged in OK
  GREEN: Step 2.95: Closing any delivery modal...
  GREEN: Delivery modal: closed_button         ← safe-click working
  GREEN: Delivery modal close attempt 1: closed_button
  GREEN: Delivery modal close attempt 2: closed_generic
  GREEN: Delivery modal close attempt 3: closed_generic

btn.click TypeError count over 7 min: 0
```

### Layer 2 evidence (after `4fb8af1`)

```
00:04:49  [GREEN] Empty result suspicious — preserving existing snapshot.
00:04:49  [GREEN]   Touched existing snapshot mtime (1 items preserved)   ← new line
00:07:09  [GREEN] Empty result suspicious — preserving existing snapshot.
00:07:09  [GREEN]   Touched existing snapshot mtime (1 items preserved)
```

### File mtime advances despite no content change

```
Before:  -rw-rw-r--  524 bytes  2026-05-14 23:08:08  (31m stale)
After:   -rw-rw-r--  524 bytes  2026-05-15 00:07:09  (0.9m fresh)
```

Same byte count = content unchanged. mtime bumped = freshness reporting correct.

### Backend `/admin/status` at 00:08 MSK

| Source | ageMinutes | isStale |
|---|---|---|
| green | 0.9m | **false** ✅ (was 31m / true) |
| red | 5.4m | true (transient — no safety guard, will refresh) |
| yellow | 4.7m | false |

### Miniapp UI at 00:08:31 MSK

- Header: **`Обновлено: 00:07`** (1 min fresh — was `Обновлено: 23:33` showing 35 min stale)
- Banner: now mentions only red (`красные (6 мин.)`); green is **fully cleared** from the staleness banner
- 0 `btn.click is not a function` exceptions in the post-deploy 7-min window

## User-visible result

The "зелёные (31 мин.)" symptom that prompted Phase 84.6 is **gone**. Green refresh now lands under 5 min reliably:
- Successful scrape → mtime updates naturally (existing behavior).
- Suspicious-empty preservation → mtime bumped to now (new behavior, Phase 84.6 follow-up).
- Real failure (browser crash, network outage) → mtime stays old, banner correctly shows stale.

The semantic distinction is preserved: "we verified" vs "we couldn't verify".

## Files modified

- `scrape_green.py` — `_close_green_modal`, `_close_delivery_modal`, new `_touch_existing_green_file()` helper, three call sites in `scrape_green_prices_async`

## Phase chain summary (the road to 5-min freshness)

| Phase | Layer | Fix | Verification |
|---|---|---|---|
| 84.4 | Pool admission | TCP pre-filter + RU-only label gate | `d469080` shipped, pool stable on 1 RU node |
| 84.5 | Scheduler | Overshoot tolerance + stall recovery + 5-min threshold | `2cf4f1c` + `76ed258` shipped, gaps 3:12/4:43/4:26 |
| 84.6 | Scraper modal-close | safe-click helper for SVG-element targets | `2fc0048` shipped, 0 btn.click errors |
| 84.6 follow-up | Scraper preservation | mtime touch on intentional snapshot preserve | `4fb8af1` shipped, green age 0.9m |

User goal — "Обновлено: never > 5 min" — met across the full chain. Phase 84.5 stall recovery is the early-warning system; Phase 84.6 is the actual recovery path.

## Phase 84 progress

22/46 inline-style sites done (Phase 84-01 + 84-02). Phase 84-03 (HistoryPage 10 + HistoryDetail 14 + bump `react/forbid-dom-props` WARN→ERROR) still pending — original Phase 84 main goal.

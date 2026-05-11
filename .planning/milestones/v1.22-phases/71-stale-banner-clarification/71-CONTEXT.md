# Phase 71 — Stale Banner Clarification — Context

**Milestone:** v1.22 UX Debt Cleanup + Tooling Polish
**Phase number:** 71
**Phase slug:** stale-banner-clarification
**Date captured:** 2026-05-12
**Requirements covered:** UX-COPY-01 + continuing OPS-15/16/17

---

## Domain

Original bug report (2026-04-06): the MiniApp shows `Обновлено: 09:36` and simultaneously displays `⚠️ Данные устарели: зелёные — товары и цены могут не совпадать с сайтом`. Both statements are correct under different definitions of "fresh":

- `Обновлено: HH:MM` = the `data["updatedAt"]` field, which is the MAX mtime across `green_products.json / red_products.json / yellow_products.json` after the merge step. When the merge ran at 09:36, it stamped the payload with 09:36. That's the "when was the rendered payload last assembled" time.
- `Данные устарели: зелёные` = per-source file age exceeds the 10-minute threshold. The merge may have written at 09:36, but it used a `green_products.json` that was last written 30 minutes ago (scraper stalling). The "data" the banner warns about is the SOURCE, not the payload.

Both labels are technically correct but they look contradictory. User-reported UX confusion.

**Scope chosen (Option B from REQUIREMENTS.md UX-COPY-01):** change banner copy from generic "Данные устарели" to the sharper "Источники устарели", and surface per-source age inline (`зелёные 30 мин.`) so the user sees which source file is old and by how much. Keep `Обновлено: HH:MM` unchanged — it IS the correct label for merged-payload time. The fix re-scopes what the banner is saying, not what the header is saying.

**Not chosen (Option A):** making the header show oldest-source-time would align the two labels but lose information — users sometimes want to know "did the backend at least assemble anything recently?". Oldest-source-time collapses that signal.

**Threshold review:** `stale_minutes=10` has been in place since v1.10. Green scraper cadence is every ~3 min via scheduler (scrape_green + merge). Red/yellow every ~3 min. In steady state a source file should be <4 min old. 10 min threshold is correct — it catches 2+ missed cycles without false-firing on a single late cycle. Keeping the threshold unchanged.

---

## SPEC Lock (from REQUIREMENTS.md UX-COPY-01)

LOCKED — planner must NOT re-litigate:

- **Banner copy change:** `⚠️ Данные устарели` → `⚠️ Источники устарели`. Narrows the scope of the warning to per-source staleness, not "everything about the payload is wrong".
- **Per-source age inline:** the existing `staleColorLabels` array currently emits `"зелёные"` / `"красные"` / `"жёлтые"`. Change to `"зелёные (30 мин.)"` / `"красные (15 мин.)"` etc., using `sourceFreshness[color].ageMinutes` rounded to integer minutes. Falls back to color-only string if `ageMinutes == null`.
- **Keep `Обновлено` label:** `Обновлено: 09:36` stays as-is. It correctly means "merged-payload time", which is the post-merge `updatedAt` timestamp stamped by the backend after the merge pipeline completes.
- **Keep 10-min threshold:** `_build_source_freshness(stale_minutes=10)` unchanged. Scheduler cadence (~3 min per color) still makes 10-min the correct "missed 2+ cycles" signal.
- **No backend schema change:** `sourceFreshness[color].ageMinutes` is already exposed by `_build_source_freshness`. Frontend consumes what's already there.
- **No other UI change:** greenMissing banner, client-side 15-min fallback bar, SSE reconnect logic — all untouched.
- **No translations:** copy is Russian-only (app language). No i18n layer.

---

## Decisions

### D1. Why "Источники" not "Данные"

"Данные" (data) is generic — user reads it as "everything is stale, don't trust anything on screen". "Источники" (sources) is narrower — user reads it as "the source files we scrape from haven't been refreshed recently, but the app is still working". Matches reality more tightly.

### D2. Why show minutes in banner not seconds

Minutes are the natural unit for scraper cadence. `30 мин.` is easy to parse; `1800 сек.` requires mental math. The existing `_build_source_freshness` already rounds to minutes via `round((_time.time() - mtime) / 60, 1)`. We drop the decimal in UI — `зелёные (30 мин.)` is more readable than `зелёные (30.4 мин.)`.

### D3. Why keep `Обновлено` label unchanged

Changing `Обновлено` would introduce churn for regular users. It already correctly means "merged payload written at HH:MM" and users are accustomed to it. The fix is the banner, not the header.

### D4. Edge case: missing file vs stale file

`_build_source_freshness` distinguishes `status: "missing"` (no file) from `status: "stale"` (file exists but old). Current banner label emits `"зелёные (missing)"` from the backend. Frontend code currently lumps both into `staleColorLabels`. Phase 71 keeps the same behavior: a missing file shows as `зелёные (нет файла)` instead of `зелёные (30 мин.)`. The existing `info?.isStale` filter catches both (`isStale: true` for both missing and stale).

### D5. Frontend vs backend change

The age-in-minutes data is ALREADY exposed in `sourceFreshness[color].ageMinutes`. Phase 71 is purely a frontend copy + label-building change. No backend diff, no API contract change.

### D6. Single atomic commit vs three

This phase is small enough (one file, ~15 LOC change + a small snapshot test) that the v1.20 / v1.21 "3 atomic commits per phase" pattern overstates the complexity. Use 2 commits:
- 71-01: frontend copy + per-source age label (App.jsx + test)
- 71-02: verify_v1.22.sh Phase 71 block + 71-VERIFICATION.md

Consistent with v1.20 late inserts (66.1 / 66.2 / 66.3) which also used 2 commits.

---

## Locked Defaults

- Banner text: `⚠️ Источники устарели: {labels.join(', ')} — товары и цены могут не совпадать с сайтом`
- Per-color format: `{color-name} ({N} мин.)` when `ageMinutes != null`, `{color-name} (нет файла)` when `status == "missing"`, plain `{color-name}` as fallback
- Threshold: 10 min (unchanged)

---

## Files Modified

- `miniapp/src/App.jsx`:
  - `staleColorLabels` useMemo rewritten to include per-source age.
  - Banner copy: `Данные устарели` → `Источники устарели`.
- `miniapp/src/__tests__/stale-banner.test.jsx` (NEW, if Vitest is wired; else skip and rely on MCP check).
- `scripts/verify_v1.22.sh` (APPEND Phase 71 block): 71-A check that Vercel-served build contains the new banner string OR the miniapp dist bundle on EC2 contains it.
- `.planning/phases/71-stale-banner-clarification/71-VERIFICATION.md` (NEW, NEEDS_OPERATOR for live MCP screenshot).

---

## Verification

- Local: `cd miniapp && npm run build` green; visual dev-server inspection matches new copy.
- Smoke 71-A: grep for `"Источники устарели"` in the compiled miniapp bundle (via Vercel or EC2 /home/ubuntu/saleapp/miniapp/dist).
- NEEDS_OPERATOR (71-VERIFICATION.md):
  - Live Chrome DevTools MCP: synthetic stale fixture on EC2 (`touch -d "30 minutes ago" data/green_products.json`), navigate to Vercel miniapp, confirm banner reads `Источники устарели: зелёные (30 мин.)` while header still shows `Обновлено: HH:MM` with a recent time. Screenshot.
  - Rollback rehearsal.
  - v1.21 + v1.20 + v1.19 regression green.

---

## Phase Boundary

**Ships:** banner copy rescoped to "Источники устарели", per-source age inline, 1-2 commits (implementation + verification docs).

**Does NOT ship:**
- Threshold re-tuning (staying at 10 min, documented rationale)
- Header label change (intentional — preserves existing semantics)
- i18n layer or translation scaffolding
- admin.html Bug Reports badge (Phase 72)
- gsd-check-todos skill polish (Phase 73)

**Acceptance gate:** miniapp build green + bundle contains new strings + MCP screenshot shows correct banner with per-source age while `Обновлено` label still shows merge time.

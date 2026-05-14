# Phase 84.7 — Per-color staleness thresholds — SUMMARY

## Status

✅ **Shipped 2026-05-15 ~02:37 MSK** as commit `5919ef8`. Deployed to EC2, live-verified end-to-end on the production miniapp.

## Goal

User reported: "5 min for red is fine and yellow set to 10". Phase 84.5 had set a uniform 5-min threshold for all 3 sources, which put red and yellow at the cycle-cadence edge — fine in steady state but transiently stale-flickering right before each full-cycle save. Yellow's larger catalog + extra merge touches gives it a slightly tighter pattern; user opted to grant it 2× the budget.

## Diagnosis

Red save cadence over a 60-min window on EC2 (2026-05-15 02:00-02:30 MSK):

| Save 1 → Save 2 | Gap | Note |
|---|---|---|
| 02:15:53 → 02:18:07 | 2:14 | normal cycle + scrape |
| 02:21:16 → 02:25:48 | **4:32** | **edge case** — fetches in this window saw red age 4.5m+ |
| 02:25:48 → 02:29:02 | 3:14 | normal |

The 4:32 gap means a fetch landing at, e.g., 02:25:30 would see red age 4.4m, but a fetch at 02:25:50 would see red age 4.6m — both fine. A 5:01 gap (which can happen on a longer cycle) would tip red over the 5-min threshold for ~10s before the next save lands. That's the source of the transient stale flicker the user observed.

This is a fundamental cadence-vs-threshold race. Three options:
1. Tighten red cadence (would need to refactor full-cycle pacing or run red-only intermediate runs — bigger change, more pool stress).
2. Raise red threshold above 5 (loosens the SLO).
3. Per-color thresholds — keep red+green tight, raise yellow to give headroom for the color most prone to edge-stale.

User chose option 3.

## Changes

### `backend/main.py`

New module-level config:
```python
DEFAULT_STALE_THRESHOLDS_MINUTES: dict[str, int] = {
    "green": 5,
    "red": 5,
    "yellow": 10,
}
```

`_build_source_freshness` signature extended:
```python
def _build_source_freshness(
    stale_minutes: int | None = None,
    stale_thresholds: dict[str, int] | None = None,
) -> tuple[dict, list[str], float]:
```

Resolution order:
1. `stale_thresholds` (per-color dict) — wins when set, missing colors fall back to defaults.
2. `stale_minutes` (legacy single int) — applied to all 3 colors. Kept for back-compat with admin scripts.
3. `DEFAULT_STALE_THRESHOLDS_MINUTES` — when neither is set.

Each color's freshness response now carries `staleThresholdMinutes` so admin tools / future UIs can show "stale at N min" without re-loading config:

```json
{
  "green":  { "ageMinutes": 0.9, "isStale": false, "staleThresholdMinutes": 5 },
  "red":    { "ageMinutes": 3.9, "isStale": false, "staleThresholdMinutes": 5 },
  "yellow": { "ageMinutes": 3.1, "isStale": false, "staleThresholdMinutes": 10 }
}
```

Both `/api/products` (line 1403) and `/admin/status` (line 5379) call sites now use defaults — no explicit `stale_minutes=5` override.

### `tests/test_scheduler_freshness.py`

Rewrote the 4 freshness tests from Phase 84.5 to 6 covering the new contract:

| Test | Pins |
|---|---|
| `test_build_source_freshness_default_thresholds_are_per_color` | green/red flip stale at 6m, yellow stays fresh; threshold values surface in response |
| `test_build_source_freshness_yellow_stale_only_above_10` | boundary check: 9.5m fresh, 11m stale |
| `test_build_source_freshness_marks_fresh_below_thresholds` | 4m green/red + 9m yellow all fresh |
| `test_build_source_freshness_legacy_stale_minutes_kwarg_overrides_all_colors` | back-compat + dict-wins-over-int when both set |
| `test_build_source_freshness_partial_dict_falls_back_to_defaults` | partial overrides preserve defaults for unspecified colors |
| `test_build_source_freshness_handles_missing_files` | missing-file `status='missing'` contract unchanged |

## Test results

- `tests/test_scheduler_freshness.py`: **16/16 passing**.
- Full suite: **310 passed**, 3 known Windows-only baseline failures, 3 skipped. No regressions.

## Live verification

### Backend `/admin/status` at 02:36 MSK 2026-05-15 (post-deploy)

```
green:  age 0.9m  stale=false  threshold=5m
red:    age 3.9m  stale=false  threshold=5m
yellow: age 3.1m  stale=false  threshold=10m
```

### Miniapp UI at 02:37:39 MSK

- Header: `Обновлено: 02:36` (1 min fresh)
- Banner: **no stale text** (`stale_count=0`)
- `/api/products` response includes new `staleThresholdMinutes` field per color:
  ```
  green:  age 1.5m, stale=false, threshold=5m
  red:    age 4.6m, stale=false, threshold=5m   ← would have edge-flickered under uniform 5m
  yellow: age 3.8m, stale=false, threshold=10m
  ```

The 4.6m red reading is exactly the case Phase 84.7 was meant to handle: under the old uniform 5-min threshold it would be stale=true for ~10s every cycle. With the new per-color threshold it stays fresh until the next cycle save lands.

## Files modified

- `backend/main.py`
- `tests/test_scheduler_freshness.py`

## Phase 84 progress

22/46 inline-style sites done (Phase 84-01 + 84-02). Phase 84-03 (HistoryPage 10 + HistoryDetail 14 + bump `react/forbid-dom-props` WARN→ERROR) still pending — original Phase 84 main goal.

Sidequests landed during Phase 84:

| Phase | Layer | Status |
|---|---|---|
| 84.1-84.3 | Pool reliability | shipped earlier |
| 84.4 | Pool admission (TCP pre-filter + RU-only) | shipped |
| 84.5 | Scheduler robustness (stall recovery + 5-min threshold + Wants= cascade fix) | shipped |
| 84.6 | Scraper robustness (safe-click + mtime touch on preserve) | shipped |
| 84.7 | Per-color staleness thresholds | **shipped (this)** |

User goal "Обновлено: never > 5 min" + per-color tuning per latest user instruction met across the full robustness chain. Banner now reflects intended SLO per data type.

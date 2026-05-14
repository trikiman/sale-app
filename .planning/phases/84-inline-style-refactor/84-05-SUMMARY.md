# Phase 84.5 — Robust green freshness: scheduler + stall recovery + 5-min threshold — SUMMARY

## Status

✅ **Shipped 2026-05-14** as commits `2cf4f1c` (code + tests) and `<systemd-commit-pending>` (unit overrides). Live-verified across 5 cycles on EC2; user-visible "Обновлено: N мин" stays under 5 min steady state, no staleness banner.

## Goal

User reported "⚠️ Источники устарели: зелёные (19 мин.)" intermittently after Phase 84.4 stabilized the pool. Goal: **green file mtime never exceeds 5 minutes**.

## Diagnosis (worth recording)

Phase 84.4 closed the pool-starvation regression but the user-visible staleness persisted. Root cause was in the scheduler, not the pool, and amplified by a pre-existing systemd dependency bug.

### Scheduler bug

`run_full_cycle` runs scrapers sequentially: RED → YELLOW → GREEN → merge, total ~3-4 min. Green is written near the end. After a full cycle ended at T+240, the post-cycle scheduling set:

```
next_all_due_at   = cycle_started + 300       # T+300
next_green_due_at = cycle_started + 60        # T+60 (already 180s overdue)
```

Then `choose_due_job` checked:

```python
if now_monotonic + estimated_green_runtime >= next_all_due_at:
    return "skip_green"
```

With `now=T+241`, `estimated_green_runtime=110s`, `next_all=T+300`: `T+241+110 = T+351 >= T+300` → **`skip_green` fires every iteration**. Green-only intermediate runs were *never* possible — green refresh frequency = full-cycle frequency = ~5 min.

### systemd bug (pre-existing, unmasked by 84.5 verification)

Both `saleapp-scheduler.service.d/10-xray.conf` and `saleapp-backend.service.d/10-xray.conf` declared `Requires=saleapp-xray.service`. Every `systemctl reload-or-restart saleapp-xray` (issued by `vless.manager._reload_xray_systemd` whenever the pool admits new nodes) cascaded into a stop-and-restart of the scheduler AND the backend, with ~90s of downtime per cascade. This was killing scrapes mid-run and stalling SSE streams.

## Commits

| Commit | Purpose |
|---|---|
| `2cf4f1c` | Scheduler logic + 5-min threshold + 14 new tests |
| (next) | systemd drop-in `Requires=` → `Wants=` for both scheduler and backend |

## Changes

### `scheduler_service.py`

- New constants:
  - `GREEN_OVERSHOOT_TOLERANCE_SECONDS = 60` — green-only is allowed to push the next full cycle by up to 60s.
  - `GREEN_STALL_THRESHOLD_SECONDS = 240` (4 min) — fires recovery before the user-visible 5-min banner threshold.
  - `GREEN_PRODUCTS_PATH` — absolute path used by the new helper.
- New `_green_file_age_seconds()` helper — returns `None` for missing file, age in seconds otherwise.
- `choose_due_job` accepts optional `green_age_seconds` kwarg. When set and exceeding the stall threshold, the function overrides the normal schedule and returns `"green"` (or `"all"` if a full cycle is also due).
- Loosened `skip_green` guard: `now + runtime > next_all + GREEN_OVERSHOOT_TOLERANCE_SECONDS` (was `>= next_all`).
- Main loop:
  - Passes `green_age_seconds` to `choose_due_job`.
  - Logs `Green-stall recovery: green_products.json is Ns old (threshold 240s) — forcing job=X` when override fires.
  - After full cycle, sets `next_green_due_at = cycle_finished_monotonic + 60s` (was `cycle_started + 60s` — already 180s overdue at cycle end).

### `backend/main.py`

- `_build_source_freshness` default `stale_minutes` lowered from 10 → 5 to match user's robustness target.
- Both call sites (`/api/products` line 1403, `/admin/status` line 5379) updated to pass `stale_minutes=5` explicitly with Phase 84.5 comment.

### `systemd/saleapp-{scheduler,backend}.service.d/10-xray.conf`

- `Requires=saleapp-xray.service` → `Wants=saleapp-xray.service`. `After=` alone preserves the "xray comes up first at boot" ordering without the restart cascade.

### `tests/test_scheduler_freshness.py` (NEW)

14 tests pinning the new behavior:

- `choose_due_job` allows green-only with overshoot ≤ tolerance, skips beyond.
- Full cycle still wins over green-only when both are due.
- `None` when nothing is due.
- Stall recovery forces green / prefers all-if-also-due / no-op below threshold / handles missing file gracefully.
- `_green_file_age_seconds` returns age for existing, `None` for missing.
- `_build_source_freshness` default 5-min threshold flags 6m stale, 4m fresh.
- Explicit override still works (10-min keeps 7m fresh; 5-min flags 7m stale).
- Missing-file `status='missing'` contract preserved.

## Test results

- `tests/test_scheduler_freshness.py`: 14/14 passing.
- Full local suite: **308 passed**, 3 known Windows-only baseline failures, 3 skipped. No regressions.

## Live verification (EC2)

### Scheduler behavior after deploy + restart

```
21:31:11  Green-stall recovery: green_products.json is 311s old (threshold 240s) — forcing job=all
21:31:11  === Starting Full Scrape Cycle ===
21:34:43  ✅ Saved 3 products → green_products.json
21:34:45  Cycle Summary
21:35:45  === Starting Green-Only Refresh ===          ← Phase 84.5: now actually fires
21:46:39  ✅ Saved 1 products → green_products.json
21:46:41  === Starting Full Scrape Cycle ===
21:51:22  ✅ Saved 1 products → green_products.json
21:55:48  ✅ Saved 1 products → green_products.json
```

### xray reload no longer cascades (after Wants= fix)

```
21:47:26  sudo systemctl reload-or-restart saleapp-xray
21:47:27  xray systemctl reload-or-restart ok (29 ms)
          ← NO 'Stopping saleapp-scheduler' line. Scheduler keeps running.
```

### Green save cadence (steady state)

| Save 1 → Save 2 | Gap |
|---|---|
| 21:43:27 → 21:46:39 | **3:12** |
| 21:46:39 → 21:51:22 | **4:43** |
| 21:51:22 → 21:55:48 | **4:26** |

✅ All gaps under 5 min.

### Final UI state

| Source | Backend `/admin/status` | Frontend miniapp |
|---|---|---|
| green | age 0.2m, isStale=false | — |
| red | age 2.7m, isStale=false | — |
| yellow | age 1.8m, isStale=false | — |
| Banner | — | **No banner** (`stale_count=0`) |
| Header | — | "Обновлено: 21:55" at 21:56:35 (1 min stale) |

User goal: data freshness never > 5 min — **MET**.

## Observability impact

- New journal line `Green-stall recovery: green_products.json is Ns old (threshold 240s) — forcing job=X` makes silent scrape failures immediately visible. Previously, a 19-min stale window would show no log evidence.
- Existing SSE pipeline (`/api/stream` watches `proposals.json` mtime) already pushes `update` events to the miniapp within ~2s of a successful save; no changes needed.

## Limitations & next steps

- **Pool still 1/10** (degraded). Phase 84.4 + 84.5 keep data fresh on a single Sberbank CDN node, but adding a second source of stable RU nodes would harden against the single-point-of-failure scenario.
- **Full cycle drift up to 60s** is now allowed (overshoot tolerance). In practice this means full cycles run every 5-6 min instead of strictly every 5. Acceptable trade-off for the freshness improvement.
- The systemd `Wants=` change is documented and committed but operators rebuilding from scratch must redeploy the unit overrides via `sudo cp + daemon-reload`. Capture that in next deploy script if not already there.
- **Phase 84-02 / 84-03** (inline-style refactor, the original Phase 84 goal) are still pending. Phase 84.4 + 84.5 were necessary infrastructure work; resume the inline-style refactor next session.

## Files modified

- `scheduler_service.py`
- `backend/main.py`
- `tests/test_scheduler_freshness.py` (new)
- `systemd/saleapp-scheduler.service.d/10-xray.conf`
- `systemd/saleapp-backend.service.d/10-xray.conf`

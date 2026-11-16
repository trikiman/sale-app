---
phase: 96
title: 7-Day Green Soak & Uptime Report
status: in_progress
started: 2026-11-16
soak_ends: 2026-11-23
---

# Phase 96 — Soak started

## Instrumentation (shipped, live)

- `backend/green_uptime.py` — dependency-free recorder + summarizer.
- Each green cycle's `finally` writes one JSONL line to
  `data/green_uptime.jsonl`: `ok`, `exit_code`, `duration_s`, `live_count`,
  `empty_reason` — read straight from the snapshot that cycle produced.
- `GET /api/admin/green-uptime?hours=168` (`X-Admin-Token`) returns the report.
- Rotates at 2 MB (one previous generation kept), torn lines are skipped.

## Verdict rules (what counts as a failure)

| Signal | Meaning | Counts as incident |
|---|---|---|
| gap > 45 min between successful cycles | UI served a stale snapshot past threshold | **yes** |
| cycle ok with `live_count == 0`, no legit reason | claimed success, nothing to show — **the v1.30 killer** | **yes** |
| cycle exits non-zero | scrape failed | lowers uptime, and creates a gap if it repeats |
| `empty_reason == source_empty` | VkusVill itself has no green tags | **no** — legitimate empty store |
| `< 24 h` or `< 10 cycles` of records | cannot judge yet | `verdict: insufficient` |

The `insufficient` verdict exists so a few clean hours can never be reported as
a healthy week.

## First records (live)

```
GET /api/admin/green-uptime?hours=168
{"verdict":"insufficient","cycles":1,"cycles_ok":1,"uptime_pct":100.0,
 "gap_incident_count":0,"false_zero_count":0,"last_ok_age_minutes":0.3}
```

`insufficient` is the correct answer with one cycle — the honest state, not a
pass.

## Acceptance for closing v1.30

- [ ] soak window reaches 168 h (2026-11-23) with ≥ 1000 cycles recorded
- [ ] `verdict: healthy` — zero gap incidents, zero false zeros
- [ ] daily check recorded in this file (see log below)
- [ ] any incident has a timestamp, stage, and the fix that followed

## First real measurements (2026-11-16, ~5 h of records)

```
{"cycles":19,"cycles_ok":15,"cycles_failed":4,"uptime_pct":78.95,
 "gap_incident_count":2,"worst_gap_minutes":99.8,
 "false_zero_cycles":0,"false_zero_count":0,"hours_recorded":5.3}
```

Reading it honestly:

- **`false_zero_count: 0`** — the milestone's actual goal is already holding: no
  cycle claimed success with nothing to show. This is the metric Phase 94 was
  built for.
- **4 of 19 cycles failed**, leaving two gaps (99.8 min and 57.1 min). The
  recorder caught them with timestamps, which is exactly why it exists.
- Current blocker: `health unhealthy [pool_below_min_healthy:0_lt_5,
  stale_cycle_1049s, stale_products_1060s, cart_add_p95_critical:21592ms]` — the
  VLESS pool is at **0** healthy nodes and `cart_add` p95 is 21.6 s.

So the picture for the week is: green data never lies about emptiness, but the
cycle is not yet reliable enough to call the soak healthy. Phase 97 made the
scheduler usable; keeping the pool alive is the next front.

## Daily log

- **2026-11-16** — instrumentation deployed (`69fad23`). First cycle recorded
  ok. Recorder verified live: `cycles=1, cycles_ok=1, verdict=insufficient`.
  Earlier the same day: green age had reached 41.8 min under the old rules; after
  the Phase 94+95 fixes, cycles resumed (7.7 min, then 1.0 min).

## Note

Phase 96 cannot be closed by a code change: it is a 168-hour observation. Until
2026-11-23 the milestone stays open, and the report says so explicitly rather
than claiming a week that has not happened.
- **2026-11-16** — ⏳ verdict `insufficient`, cycles 1 (uptime 100.0%), gaps 0, false zeros 0, last ok 3.6 min ago.
- **2026-11-16** — ⏳ verdict `insufficient`, cycles 19 (uptime 78.95%), gaps 2, false zeros 0, last ok 18.0 min ago.

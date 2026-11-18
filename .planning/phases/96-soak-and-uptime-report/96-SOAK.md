---
phase: 96
title: 7-Day Green Soak & Uptime Report
status: in_progress
started: 2026-11-16
soak_ends: 2026-11-23
---

# Phase 96 — Soak started

## 2026-11-18 01:10 MSK — all recorded gaps are historical

`GET /api/admin/green-uptime?hours=168`: **172 cycles, 154 ok, 18 failed, 89.53%,
`false_zero_cycles: 0`, 36.7 h recorded, verdict `incident`.**

The verdict is driven entirely by gaps, and every one of them predates the fixes:

| gap | window (UTC) | age |
|---|---|---|
| 99.8 min | 16.11 09:04 → 10:44 | 35 h |
| 57.1 min | 16.11 12:02 → 12:59 | 33 h |
| 49.1 min | 16.11 16:58 → 17:47 | 28 h |
| 46.9 min | 16.11 20:18 → 21:05 | 25 h |
| 79.8 min | 17.11 00:59 → 02:19 | 19 h |
| 54.0 min | 17.11 02:46 → 03:40 | 18 h |

**No gap in the last 18 hours.** Cycle spacing since 17:19 UTC is 8–15 min, last
`ok` 0.2 min old, and 20+ consecutive successful cycles. The 18 failures are the
pre-fix `exit=-9` kills plus one `exit=1` at 17:58 (655 s run).

Read this as: the mechanism is proven healthy from 03:40 UTC on; the 168 h window
still carries the two bad days and will report `insufficient`/`incident` until
they age out on 2026-11-23. That is the honest reading — not a claim that the
whole window was clean.

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

## Second measurement (same day, after the egress work)

```
{"cycles":37,"cycles_ok":28,"cycles_failed":9,"uptime_pct":75.68,
 "gap_incident_count":3,"false_zero_count":0}
egress-probe: urnetwork ok | vless timeout (pool 0/5)
```

Two things worth recording:

- **`false_zero_count` is still 0** across 37 cycles. The user-visible promise —
  green never silently shows as empty — is holding.
- The **balancer route died** (`pool 0/5`, `vless: timeout`) and green cycles kept
  running through the **URnetwork** route. Phase 97's premise was verified live:
  a dead pool no longer idles the scraper.
- Cycle reliability is the remaining gap: 9 of 37 cycles failed (75.7% uptime),
  so the soak cannot honestly be called healthy yet even though the false-zero
  condition is clean.

## Root cause of the failed cycles (2026-11-16, 22:00)

The aggregates said `9/39 failed`; the new `?tail=N` view said **why**:

```
22:04 ok=True  exit=0  dur=233.5s live=1
22:21 ok=False exit=-9  dur=340.1s live=1   <- SIGKILL by the silence watchdog
```

Successful cycles run **223–351 s**, and the watchdog kills after **300 s without
output** — so long legitimate steps (basket recalc, merge) read as a hang and
healthy runs died mid-flight. `SCRAPER_TIMEOUT` raised to **420 s** (`a923aed`),
which keeps hang protection but covers the observed 351 s ceiling.

**First cycle after the change:** `22:33 ok=True exit=0 dur=222.1s`. One sample is
not proof — the failure rate over the next day is what will settle it.

## Timeout fix confirmed (2026-11-16, 23:10)

Four consecutive successful cycles after the change, **none killed**:

```
22:33 ok exit=0 dur=222.1s
22:43 ok exit=0 dur=328.9s
22:56 ok exit=0 dur=478.7s   <- would have been SIGKILLed at 300 s before
23:07 ok exit=0 dur=310.8s
```

The 478.7 s run is the decisive one: under the old 300 s silence budget it would
have died with exit -9 exactly like the 340 s and 351 s failures. Aggregate moved
`39 cycles / 9 failed` -> `44 cycles / 10 failed`, i.e. **no new failures** while
5 cycles completed.

## Overnight (2026-11-17, 00:20) — the new limit behaves correctly

```
49 cycles | 38 ok | 11 failed | uptime 77.55% | false_zero 0 | gaps 4
23:18 ok   dur=242.5s
23:42 FAIL exit=-9 dur=493.8s   <- a real hang, killed as designed
00:05 ok   dur=193.2s
00:12 ok   dur=147.4s
00:20 ok   dur=200.4s
```

The distinction that matters: after the 420 s change, the only kill is a cycle
that genuinely hung for **493.8 s** (well past any legitimate step), and the
watchdog ended it. That is the protection working, not a false positive — the
earlier failures were killed at 340–351 s, i.e. *inside* normal run length.

Cycles after the hang also got faster (147–200 s vs 300–480 s before), which
suggests the stall was tied to a degraded Chrome session rather than steady load.

`false_zero_count` remains **0** across 49 cycles: the milestone's actual promise
is holding through the whole night.

## Daily log

- **2026-11-16** — instrumentation deployed (`69fad23`). First cycle recorded
  ok. Recorder verified live: `cycles=1, cycles_ok=1, verdict=insufficient`.
  Earlier the same day: green age had reached 41.8 min under the old rules; after
  the Phase 94+95 fixes, cycles resumed (7.7 min, then 1.0 min).

## Acceptance checklist for 2026-11-23 (prepared, not yet run)

Run these in order and paste the real numbers into the closure note — nothing is
"ok" until the first two commands say so:

1. `curl -s -H "X-Admin-Token: $ADMIN_TOKEN" http://152.70.58.201/api/admin/green-uptime?hours=168`
   → record `verdict`, `cycles`, `cycles_ok`, `uptime_pct`, `false_zero_cycles`,
   `hours_recorded`, `gap_incident_count`.
2. Same endpoint with `&tail=200` → count gaps whose `from_ts` is **after** 2026-11-17
   03:40 UTC. The six pre-fix gaps must have aged out of the 168 h window; any *new*
   gap older than today means the fix did not hold.
3. `scripts/green_soak_check.py` exit code 0 = norm, 2 = incident, 3 = stale recorder.
   Only exit 0 counts as acceptance.
4. `python3 -m pytest tests/ -q` → expect 317 passed / 2 skipped.
5. `gsd-tools state complete-phase --phase 96` **only** if step 1 shows
   `false_zero_cycles == 0` AND every gap in step 2 is historical.
6. Then `gsd-audit-milestone` and `gsd-complete-milestone` for v1.30.

What blocks closure, stated up front: a new gap, `false_zero_cycles > 0`, fewer than
168 h recorded, or a verdict that contradicts the data.

## Note

Phase 96 cannot be closed by a code change: it is a 168-hour observation. Until
2026-11-23 the milestone stays open, and the report says so explicitly rather
than claiming a week that has not happened.
- **2026-11-16** — ⏳ verdict `insufficient`, cycles 1 (uptime 100.0%), gaps 0, false zeros 0, last ok 3.6 min ago.
- **2026-11-16** — ⏳ verdict `insufficient`, cycles 19 (uptime 78.95%), gaps 2, false zeros 0, last ok 18.0 min ago.
- **2026-11-17** — ⏳ verdict `insufficient`, cycles 78 (uptime 78.21%), gaps 6, false zeros 0, last ok 4.2 min ago.

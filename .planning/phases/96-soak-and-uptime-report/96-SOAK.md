---
phase: 96
title: 7-Day Green Soak & Uptime Report
status: in_progress
started: 2026-11-16
soak_ends: 2026-11-25
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
they age out between 2026-11-23 and 2026-11-25. That is the honest reading — not a claim that the
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

- [ ] soak window reaches 168 h (clears 2026-11-25 06:21 UTC) with ≥ 1000 cycles recorded
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

## False zero #1: 20.11 05:12:12 UTC — the milestone's core failure, once

`false_zero_cycles` went from 0 to **1**. The record says exactly what happened:

```
20.11 05:12:12  ok=True  exit=0  live=0  empty_reason='unknown_empty'
```

By the definition this phase is built on — a cycle that exits 0 reporting
`live_count == 0` without VkusVill's own `source_empty`/`missing` reason — that is a
false zero: the run **claimed success with nothing to show**. `unknown_empty` is the
scraper's honest way of saying "the green section was empty and VkusVill did not show
its «Зелёных ценников сейчас нет» banner, so I cannot prove the emptiness is real".
The neighbouring cycles at 05:03 and 05:34 both recorded `source_empty`, so the site
really was empty that night — but "probably empty" is not the standard this milestone
set, and I am not going to relabel a recorded failure as a pass.

Consequences, stated plainly:

- acceptance **cannot** be read on 26.11 — the false zero sits inside the 168 h window;
- the window clears 168 h after it: **2026-11-27 05:12 UTC = 08:12 MSK**;
- `scripts/green_soak_check.py` now treats false zeros as first-class (exit 2 for any
  beyond the diagnosed one), instead of letting them hide behind "only known gaps";
- `scripts/phase96_acceptance.py` uses the new epoch and still fails on
  `false_zero_cycles != 0`.

What I have NOT done: change the definition, delete the record, or reclassify it as
`source_empty` after the fact.

**The repeat is now closed at the root** (`green_empty.py` + `scrape_green.py`): an
empty green list is a success only when VkusVill itself proves it — a non-empty list, or
the explicit "Зелёных ценников сейчас нет" banner. `unknown_empty` now **fails the run**
(exit 1), keeps the previous snapshot instead of overwriting it with an unproven empty
one, and is recorded as a failed cycle rather than a false zero. The rule lives in one
dependency-free function so it cannot grow a second implementation; a test asserts the
scraper imports it and does not redefine it.

## Gap #8 (the first post-fix gap): 19.11 04:54 → 06:18 UTC, 84.0 min

**This one is on us, not history.** It started after the fix mark, so the daily check
correctly raised exit 2. Symptoms, from the cron report and `/admin/logs`:

- green ran, Chrome came up, login OK, `Loaded 48/48 cookies via CDP`, then
  `Green section: found 0 items`, `live_count=0`, `Seed item: no_button_found`,
  `delivery picker not_found`, and page reloads hitting the 45 s deadline;
- failure mode was repeated `exit 1` with `TimeoutError` — **no SIGKILL**, so the
  deadline work did its job: nothing hung, runs simply failed fast and often;
- the stale snapshot was preserved (`58 items`, mtime touched), so `false_zero_cycles`
  stayed **0** — the protocol held even while scraping was broken.

Probable cause (inference, not proven — the logs of that window are gone):
the only working egress was URnetwork. `vless` has been timing out for hours and the
dynamic pool sits at 0 nodes, so every navigation depended on one route; when it
slowed, all three navigation attempts burned their deadlines. Measured now, after
recovery: `urnetwork ok 200 8.9 s`, `vless timeout 13.1 s` — a single-route setup with
no headroom. Closing the gap at 06:18 happened on its own, which fits a transient
route stall rather than a site-layout change.

**Consequence for acceptance:** the 168 h window now clears only after *this* gap
leaves it — **26.11 06:18 UTC = 09:18 MSK**. Stated bluntly: with one gap every ~1.5 days,
waiting for a fully clean 168 h window may never succeed, and each new gap pushes the
date. That is a decision for the operator (fix the egress / accept a criterion based on
time-without-false-zero), not something to paper over by re-reading the numbers.

## Risk measurement, 2026-11-19 00:55 UTC — how close are we to a new gap?

The criterion is a gap > 45 min, and failures still happen (25 of 342 cycles), so the
question is how much slack sits between a failure burst and the threshold. Measured
over the last 200 cycles (33.2 h, from `?tail=200`):

- 192 ok, 8 failed — max **failure run = 2** (runs: 1, 2, 1, 1, 1, 2), never 3;
- max gap between successful cycles **24.3 min** (18.11 22:18 → 22:42); the only
  larger gap is the known 69.4 min incident, which predates the 45 s evaluate deadline;
- average gap 10.4 min.

So the worst observed burst uses ~54% of the 45-minute budget. At ~200–500 s per failed
run, a gap stays under the threshold as long as failures do not chain past two. That is
the standing risk for 25.11: **not hangs (those are gone — 0 SIGKILL), but a 3-in-a-row
burst of ordinary errors.** No code change was made on the strength of one measurement;
if a third consecutive failure ever appears in the series, the fix is to force a Chrome
restart between cycles rather than let the burst ride.

## Date correction: acceptance reads **2026-11-26 09:18 MSK** (was 2026-11-25, before gap #8)

Stated plainly because it changes the plan: with the criterion unchanged
(`healthy` = zero gaps > 45 min **and** zero false zeros inside the 168 h window),
2026-11-23 cannot produce `healthy` — the window still contains six historical gaps.
Each gap leaves the window 168 h after it *ended*, so the last one dictates the date:

| gap | window of the gap (UTC) | leaves the 168 h window |
|---|---|---|
| 99.8 min | 16.11 09:04 → 10:44 | 23.11 10:44 |
| 57.1 min | 16.11 12:02 → 12:59 | 23.11 12:59 |
| 49.1 min | 16.11 16:58 → 17:47 | 23.11 17:47 |
| 46.9 min | 16.11 20:18 → 21:05 | 23.11 21:05 |
| 79.8 min | 17.11 00:59 → 02:19 | 24.11 02:19 |
| 54.0 min | 17.11 02:46 → 03:40 | 24.11 03:40 |
| **69.4 min** | **18.11 05:12 → 06:21** | **25.11 06:21** |

The 7th gap is the one that matters: it happened *after* the "fixed since 17.11"
line, so a run that only waits for the 16–17.11 gaps to age out would still read
`incident`. Acceptance therefore reads **2026-11-25 09:21 MSK** at the earliest — the
first moment the series holds 168 h with no gap at all. Nothing else changes: the
criterion is not relaxed, the date follows from arithmetic.

## Acceptance checklist (read 2026-11-25 09:21 MSK or later)

Run these in order and paste the real numbers into the closure note — nothing is
"ok" until the first two commands say so:

0. `python scripts/phase96_acceptance.py` — runs checks 1-2 mechanically and prints
   PASS/FAIL per criterion (exit 0 = all pass, 2 = a criterion failed, 3 = endpoint
   unreachable). It never closes anything; steps below stay human-owned.

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
   `false_zero_cycles == 0` AND `gap_incident_count == 0` (the 168 h window is clean,
   i.e. no gap at all — historical or new — sits inside it).
6. Then `gsd-audit-milestone` and `gsd-complete-milestone` for v1.30.

What blocks closure, stated up front: a new gap, `false_zero_cycles > 0`, fewer than
168 h recorded, or a verdict that contradicts the data.

## Note

Phase 96 cannot be closed by a code change: it is a 168-hour observation. Until
2026-11-25 the milestone stays open, and the report says so explicitly rather
than claiming a week that has not happened.
- **2026-11-16** — ⏳ verdict `insufficient`, cycles 1 (uptime 100.0%), gaps 0, false zeros 0, last ok 3.6 min ago.
- **2026-11-16** — ⏳ verdict `insufficient`, cycles 19 (uptime 78.95%), gaps 2, false zeros 0, last ok 18.0 min ago.
- **2026-11-17** — ⏳ verdict `insufficient`, cycles 78 (uptime 78.21%), gaps 6, false zeros 0, last ok 4.2 min ago.
- **2026-11-18** — 🔴 verdict `incident`, cycles 192 (uptime 90.62%), gaps 6, false zeros 0, last ok 0.6 min ago.
- **2026-11-18** — 🔴 verdict `incident`, cycles 192 (uptime 90.62%), gaps 6, false zeros 0, last ok 0.8 min ago.
- **2026-11-18** — 🔴 verdict `incident`, cycles 213 (uptime 90.61%), gaps 7, false zeros 0, last ok 47.9 min ago.
- **2026-11-19** — 🔴 verdict `incident`, cycles 346 (uptime 92.77%), gaps 7, false zeros 0, last ok 14.4 min ago. ⏳ window still holds 7 pre-fix gap(s); acceptance 2026-11-25
- **2026-11-19** — 🔴 verdict `incident`, cycles 367 (uptime 91.01%), gaps 8, false zeros 0, hours 68.8/168, last ok 65.7 min ago. 🚨 NEW post-fix gap: с 2026-11-19 04:54:30 UTC, открыт на момент проверки; green scrape exit 1 (green section: 0 items, seed no_button_found, reload timeout 45s); dynamic VLESS pool=0 ~9 ч (refresh streak=27, 444 quarantine), работа через manual-seed bridge 10808. Не исторический гэп — фиксы не держат.
- **2026-11-19** — 🔴 verdict `incident`, cycles 412 (uptime 90.53%), gaps 8, false zeros 0, last ok 6.1 min ago. ⏳ window still holds 8 pre-fix gap(s); acceptance 2026-11-25
- **2026-11-19** — 🔴 verdict `incident`, cycles 412 (uptime 90.53%), gaps 8, false zeros 0, last ok 6.5 min ago. ⏳ window still holds 8 known gap(s) (pre-fix + diagnosed post-fix); acceptance 2026-11-26 06:18 UTC (09:18 MSK)
- **2026-11-20** — 🔴 verdict `incident`, cycles 522 (uptime 90.8%), gaps 8, false zeros 1, last ok 4.0 min ago. ⏳ 1 diagnosed false zero(s) in window; acceptance 2026-11-27 05:12 UTC (08:12 MSK)
- **2026-11-20** — 🔴 verdict `incident`, cycles 524 (uptime 90.84%), gaps 8, false zeros 1, last ok 5.3 min ago. ⏳ 1 diagnosed false zero(s) in window; acceptance 2026-11-27 05:12 UTC (08:12 MSK)

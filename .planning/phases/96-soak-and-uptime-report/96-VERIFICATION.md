---
phase: 96
title: 7-Day Soak & Uptime Report
status: passed
verified_at: 2026-11-28T09:25:00+03:00
verifier: hermes (autonomous, prod read-only + one file deploy)
---

# 96 — Verification

Acceptance was judged on the **live prod record**, not on a replay or a projection.
The one-shot collector `~/.hermes/scripts/saleapp_acceptance_check.sh` (cron
`08440c65ff15`, `no_agent`, no LLM in the path) was also run by hand at 09:21 MSK to
confirm the same verdict independently of the schedule.

## Mechanical gate — `scripts/phase96_acceptance.py`

```
verdict: healthy
cycles: 928 (890 ok / 38 failed), uptime: 95.91%
  [PASS] false_zero_cycles == 0 — 0
  [PASS] gap_incident_count == 0 — 0
  [PASS] hours_recorded >= 167.25 (168 h minus 45 min partial cycles) — 167.8
  [PASS] no gap after acceptance epoch — 0 post-epoch gap(s)

✅ All mechanical checks passed.
VERDICT: acceptance MET (phase96_acceptance exit 0) — phase 96 can be closed
```

`green_soak_check.py` in the same run: `✅ verdict healthy, cycles 928 (uptime 95.91%),
gaps 0, false zeros 0, last ok 2.0 min ago`, exit 0.

## How the last blocker cleared

| moment (MSK) | gaps | note |
|---|---|---|
| 27.11 22:30 | 2 | gap #10 and #11 both inside the 168 h window |
| 27.11 22:50 | 1 | gap #10 (`1795204232…1795206951`) aged out |
| 28.11 08:20 | **0** | gap #11 (`1795240071.544` = 21.11 08:47:51 MSK) aged out at 08:47:51 |

The `from_ts` rule predicted both dates to the minute — the gap list is computed, not
curated. Verdict went `incident` → `healthy` on its own, with no intervention.

## Micro-batch proof (the manual fifth step)

`scripts/batch_proof_check.py` at 08:5x MSK, live `/admin/logs?n=300`:

```
lines=300 hits=8 distinct_batch_ranges=6 ranges=0-10,10-20,20-30,30-40,40-50,50-56
  [GREEN]   [GREEN] Added 56/56 items to cart
BATCH PROOF: multi-batch observed — 6 distinct ranges in one window
exit=0
```

Six distinct ranges in one cycle, 56/56 items added — the multi-batch path the milestone
was waiting for, observed and not inferred.

## Deploy of the parked fix (`66c124e`)

- Staged as `~/saleapp/.scrape_green.py.new`, sha256 `bebef9475c535652…`, identical to
  the local file.
- Verified on the **server** interpreter before activation: `venv/bin/python` imports it
  with real deps and the classifier answers `(28,40,40,600) → preserve_ok`,
  `(5,40,40,600) → preserve_fail`, `(400,400,400,7200) → save_new`.
- Activated 28.11 09:23 MSK: original kept as `scrape_green.py.bak-pre66c124e-20261128-0623`
  (193 102 B), new file in place, `ast.parse` OK, `classify_green_count_mismatch`
  present. No service restart needed — `scheduler_service.py` spawns the scraper per
  cycle.

## What this does and does not prove

Proven: green never reported a false zero across 928 measured cycles; the 168 h window
closed with no gap; the multi-batch add ran end to end on prod; the short-scrape fix is
loaded on prod and answers correctly.

Not proven: the fix's effect on live uptime (it applies from the next cycle onward, and
its measurable result is a *future* reduction in failed cycles); `ADMIN_TOKEN` rotation,
which is still pending and would require touching `.env` + restarting the backend.

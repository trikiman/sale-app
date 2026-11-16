---
phase: 95
title: Green Cycle Self-Healing
status: passed
verified: 2026-11-16
---

# Phase 95 — Verification

## Criterion 1 — Chrome launch budget

**Passed (code + live).** `chrome_stealth.launch_stealth_browser`: 30 attempts,
relaunch at 0/8/16 s, child stdout+stderr to `chrome_scraper_<port>.log`.
Live: no `Chrome not available on port 19222` after deploy; green cycles complete.

## Criterion 2 — CDP target swap recovery

**Passed, and a real bug was found by the new tests.**
`tests/test_green_recovery.py` injects `ConnectionClosedError` into evaluate and
asserts recovery; **it exposed `UnboundLocalError` in `_reacquire_page`** — when
all three re-navigation attempts raised, `page` was never bound and
`return page` blew up exactly at the recovery point, converting a recoverable
target swap into a dead cycle. Fixed (`page = None` before the loop).

## Criterion 3 — delivery slot never clicks arbitrary controls

**Passed.** Only modals matching `доставк|самовывоз|времени доставки|слот` are
candidates; the time-slot regex (`сегодня|завтра|ЧЧ:ММ`) gates the click. Test
`test_ensure_delivery_slot_clicks_nothing_without_a_delivery_modal` asserts zero
picks and a definitive status when no such modal exists.

## Criterion 4 — fault injection at each stage

**Passed.** 10 tests in `tests/test_green_recovery.py`, no Chrome, no network:

```
$ python3 -m pytest tests/test_green_recovery.py -q
..........                                        [100%]
10 passed
```

Covered: dead WS mid-evaluate → 3 retries on a fresh handle; retry budget stays
3 (no unbounded loop); non-WS errors surface immediately and are never retried;
`_reacquire_page` retries then returns instead of hanging; no delivery modal →
zero clicks; existing slot short-circuits; delivery text/time filter still
present; recovery helpers still called by the cycle (≥3 call sites).

## Criterion 5 — no lock held by a dead process

**Passed as code + boundary tests; the 168-hour absence claim moved to Phase 96.**
`backend/run_guard.is_zombie_run()` + per-run `threading.Timer(900 s)` that kills
the child and is cancelled in `finally`. `tests/test_run_guard.py` (13 tests)
pins the bounds and the wiring, plus the source-level assertions that the skip is
behind the zombie check and the timer is both created and cancelled.

**Measured:** before deploy the green snapshot sat at 41.8 min untouched with
"Already running, skipping" every tick; after deploy, 7.7 min and cycles
resuming. A two-week absence cannot be proven by one deploy — that is Phase 96's
soak, not a gap in this phase's work.

## Suite

```
279 → 294 passed  (15 new: 10 recovery, 13 run-guard, minus overlap with 9 guardrail tests)
1 failed: test_vless_xray.py::test_start_succeeds_when_port_opens — pre-existing, xray port timing
```

---
phase: 95
title: Green Cycle Self-Healing
status: in_progress
---

# Phase 95 — Progress

## Done and verified live

**95-01a — Chrome launch budget (criterion 1).** `chrome_stealth.launch_stealth_browser`
waited 10 s with a single launch attempt; on the 1 vCPU / 1 GB box Chrome needs
15-25 s to expose CDP and a launch can die instantly under memory pressure. Now
30 attempts with relaunch at 0/8/16 s, and the child's stdout+stderr go to
`chrome_scraper_<port>.log` with the pid printed — `Chrome not available on port
19222` can no longer hide its cause.

**95-01b — CDP target swap recovery (criterion 2).** `_reacquire_page(browser)`
re-navigates with 3 retries and returns a fresh handle; `_safe_js()` retries 3x
(live tab first, full re-navigation after); `_close_delivery_modal`, the
green-section scroll and `_inspect_green_section` each catch a dead-WS error and
recover. Before this, roughly every other cycle exited 1 with
`no close frame received or sent`.

**95-01c — delivery slot never clicks arbitrary controls (criterion 3).** The
picker only considers modals whose text matches
`доставк|самовывоз|времени доставки|слот`; a generic "click the first button"
fallback had been landing on the "Скоро исчезнут с полок" filter and
destabilising the page. With no delivery modal it returns `no_slot_found` and
does nothing.

**95-02 — zombie run guard (criterion 5, partial).** The `running` flag survived
a dead cycle because the worker thread blocks in `for line in proc.stdout` on a
live-but-silent child, so its `finally` never ran; every later tick logged
"Already running, skipping" and green went 42 minutes untouched. Now:
`is_zombie_run()` (`backend/run_guard.py`) plus a per-run
`threading.Timer(_RUN_STALE_SECONDS)` that kills the child and cancels in
`finally`. 13 tests pin the bounds (900 s = 3x the 300 s scraper ceiling) and the
wiring.

**Measured effect:** green snapshot age fell from 41.8 min to 7.7 min after
deploy, `green=42`, `greenSuppressed=null`, `greenAlerts=null`.

## Not done — and therefore NOT marked complete

- **Criterion 4 — fault injection per stage.** The four abort stages were
  reproduced by real traffic and recovered in production logs, but there is no
  synthetic test that injects "Chrome down", "dead WS after seed", "dead WS after
  cart clear" and "no delivery modal" and asserts the cycle ends within its retry
  budget. Without it a future refactor can silently un-wire the recovery paths.
- **Criterion 5 — two weeks of scheduler output.** One deploy cannot prove an
  absence over weeks; this needs the soak window from Phase 96.

Both are honest gaps, not oversights. Phase 95 stays open until 95-03 lands.

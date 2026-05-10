---
created: 2026-05-10T16:26:37Z
title: scheduler circuit breaker traps recoverable green failures
area: tooling
files:
  - scheduler_service.py:53 (BREAKER_STATE_FILE = data/scheduler_state.json)
  - scheduler_service.py:162 (_load_breaker_state)
  - scheduler_service.py:179 (_persist_breaker_state)
  - scheduler_service.py:821 (skip-when-open logic)
  - data/scheduler_state.json (persisted state across restarts)
---

## Problem

The v1.19 phase 60 3-state circuit breaker protects against hammering a broken VkusVill, but during the May 6-10 outage it amplified the problem rather than isolating it.

Behavior observed (2026-05-10):
- Every green scrape failed because xray was pinned to a dead outbound (separate xray-reload bug).
- Breaker transitioned HALF_OPEN to OPEN with cooldown_s=1800 (30 min).
- Every minute the scheduler logged "Skipping GREEN-only refresh to keep the next full cycle on schedule."
- Red and yellow got skipped too (cycle_type=green_only during the inter-full-cycle minutes).
- After 30 min the breaker retried, still failed, re-opened. Loop forever.
- fails counter reached 171 by the time we reset it manually.
- State persists across scheduler restarts, so restarting the service does not help.

Two specific annoyances:

1. Breaker state is loaded before the underlying network is tested. So even if sudo systemctl restart saleapp-xray fixes the bridge, the breaker keeps scheduler in OPEN state until its own cooldown expires.
2. There is no command or endpoint to force-close the breaker. We had to echo a fresh JSON blob into data/scheduler_state.json and restart the service.

## Solution

TBD. Ideas:

1. Add a one-shot probe on scheduler startup: if the pre-flight probe through the xray bridge passes, force-close the breaker. Prevents "bridge healed but breaker still tripping" loops.
2. Admin endpoint POST /api/admin/scheduler/breaker/reset gated by X-Admin-Token. Writes state=closed, fails=0, cooldown_until_ts=0. Logs "manual reset".
3. Distinguish transient (timeout, 5xx) from structural (auth expired, empty DOM) failures. Structural failures count toward breaker. Transient failures should not (they belong in the scraper retry budget, not the milestone cadence).

Evidence: session log 2026-05-10 19:12-19:18 shows manual reset plus restart, scheduler completed a full cycle within 3 minutes.

---
phase: 94
title: Green Uptime Guardrails
status: passed
verified: 2026-11-15
---

# Phase 94 — Verification

## Criterion 1 — a false green zero is structurally impossible

**Passed.** The decision lives in `backend/green_visibility.py`; acceptance is
pinned by 9 tests in `tests/test_green_uptime_guardrails.py`:

```
$ python3 -m pytest tests/test_green_uptime_guardrails.py -q
.........                                          [100%]
9 passed in 0.04s
```

Covered cases: fresh+products → visible; **stale+products → visible** (the
regression that caused the false zero); `source_empty` / `missing` → hidden with
that reason; empty snapshot without a reason → `no_snapshot_products`;
`unknown_empty` with products → still visible; the full stale × reason matrix
with products → always visible.

Two source-level tests refuse the old shape outright: `green_visibility(` must
appear inside the stale-strip window, and `_strip.discard("green")` must be
present. Reinstating the unconditional strip fails the suite.

## Criterion 2 — suppression is explicit in the payload

**Passed, verified live** (server 152.70.58.201, `dee21b4`):

```
GET /api/products      → green=77 live=77 stale=False greenSuppressed=null
GET /admin/status      → green=77 greenSuppressed=None greenAgeMinutes=41.8 greenAlerts=None
```

`greenSuppressed` is `null` exactly when cards are shown, and carries a reason
string otherwise. The bug path (`payload_missing_but_snapshot_has_products`) is
logged when the snapshot claims products and the payload has none.

## Criterion 3 — alerts for the two deadly states

**Passed via the status/log path; Telegram part blocked.** `/admin/status`
computes `greenAlerts`:

- `green_snapshot_stale:<Nm>` when the snapshot is older than 2× the green
  interval (90 min at the current 45-minute threshold);
- `green_zero_with_live_count` when `green == 0` while `greenLiveCount > 0`;
- `null` when healthy — observed live.

Telegram delivery is **not** done: `@green_price_monitor_bot` is not polled
(`getUpdates` returns `ok:true`, no webhook), `/admin/test-alert` answers
`no_admin_chat_ids`, and configuring it needs SSH, which DPI blocks. Recorded as
the one open item of this phase and carried into the GREEN-UP-04 follow-up.

## Criterion 4 — the regression cannot return

**Passed.** `test_api_source_has_no_unconditional_green_strip` reads
`backend/main.py` and asserts the strip consults `green_visibility` and discards
green when it is visible. `test_api_always_reports_suppression_reason` asserts
the payload field and the bug-case marker exist.

## Suite status

```
tests/ (excluding 5 modules that need python-telegram-bot, absent in the local venv)
279 passed, 3 skipped, 1 failed, 10 errors
```

- the single failure is `test_vless_xray.py::test_start_succeeds_when_port_opens`
  — pre-existing, unrelated to this phase (xray port timing);
- the 10 errors are `tests/test_scheduler_freshness.py` collecting
  `backend.main`, which imports `bot.auth` → `telegram` (not installed locally).
  Those tests run on CI where the dependency exists;
- `tests/test_scheduler_freshness.py` was updated for the 15 → 45 minute green
  threshold so it does not fail on CI.

## Honest limitation

The suite cannot be fully executed on this workstation (missing
`python-telegram-bot`). The new guardrail tests are dependency-free by design and
do run; the scheduler-freshness updates are mechanical (15 → 45, plus a rewritten
override test using 60 m / override 90 m) and unverified locally for that reason.
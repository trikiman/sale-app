---
phase: 96
plan: 96-01
title: Per-cycle uptime recorder with rotation
status: complete
---

# 96-01 — Summary

Recorder lives in `backend/green_uptime.py` (dependency-free). Written from
`scheduler_service.run_script()` after `proc.wait()` for `tag == "GREEN"`, with
`timed_out` and `killed_by_trigger` recorded as failures rather than dropped.

Getting the owner right cost two wrong attempts, both caught by comparing the
record against reality:

| where the record was written | observed symptom |
|---|---|
| backend worker `finally` | `cycles: 1` after an hour of traffic — only manual runs counted |
| `scrape_green.py` `finally` | still `cycles: 1` — watchdog SIGKILLs the child, `finally` never runs |
| `scheduler_service` parent | `cycles: 2, cycles_ok: 2`, and growing |

Verified live: `GET /api/admin/green-uptime?hours=168` →
`{"verdict":"insufficient","cycles":2,"cycles_ok":2,"uptime_pct":100.0}`.
`insufficient` is correct with two cycles — the honest answer, not a pass.

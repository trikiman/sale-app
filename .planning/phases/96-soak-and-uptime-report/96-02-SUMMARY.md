---
phase: 96
plan: 96-02
title: /admin/green-uptime aggregation + daily soak check
status: complete
---

# 96-02 — Summary

Endpoint and daily check delivered. 14 tests in `tests/test_green_uptime.py`,
including a synthetic healthy week (one cycle per minute for 168 h), a 4-hour
hole, trailing dead air, a false-zero run, a `source_empty` run that must **not**
count, and a torn JSONL line.

Live samples:

```
{"verdict":"insufficient","window_hours":168,"cycles":1,"cycles_ok":1,
 "uptime_pct":100.0,"gap_incident_count":0,"false_zero_count":0}
```

Daily line written to `96-SOAK.md` by `scripts/green_soak_check.py`
(exit 0 healthy, 2 incident, 3 unreachable).

**Still open — Phase 96 as a whole:** the 168-hour window. Instrumentation is
done; the verdict can only be read on 2026-11-23.

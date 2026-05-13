# Phase 77 — Pool Self-Heal Hardening
**Milestone:** v1.24 Pool Self-Heal Hardening + Outage UX
**Requirements:** REL-16, REL-17, REL-18, REL-19 (+ optional OBS-08)
**Started:** 2026-05-13

## Goal

Reduce VLESS pool recovery time from ~1h to ≤10 min after full collapse. Eliminate the 19-refreshes-in-15-min thrash observed 2026-05-13 by adding persistent quarantine memory, refresh throttle, earlier low-water-mark warning, and scheduler graceful degrade.

## Root Causes (from live 2026-05-13 outage)

1. **No quarantine memory across refreshes** — every refresh re-probes the same 231 RU-filtered nodes from scratch. Dead nodes from 2 min ago get re-tested. Wasted probe time = slower recovery. `vkusvill_cooldown` exists but only for "VkusVill blocked" signal, not "probe failed to connect".

2. **Refresh trigger cascade** — every failing scrape triggers `ensure_pool()` → `refresh_proxy_list()`. 3 scrapers × 3 min/cycle → 1 refresh per minute at best. At worst (observed): 19 refreshes in 15 min.

3. **`MIN_HEALTHY = 7` low-water mark triggers too late** — pool can drop 25→6 in one cycle; we react only after the fact.

4. **Scheduler hard-fails with exit 1 when pool is empty** — creates log noise, wastes retry cycles, doesn't help recovery.

## Decision

### REL-16: Persistent probe-failure quarantine

New file: `data/pool_quarantine.json`:
```json
{
  "quarantined": {
    "72.56.235.141:443": {
      "reason": "probe_timeout",
      "first_failed_at": 1778588586.3,
      "last_failed_at": 1778588586.3,
      "fail_count": 1,
      "expires_at": 1778589786.3
    },
    ...
  }
}
```

TTL: **20 min** (configurable `QUARANTINE_TTL_S = 1200`). Host with `fail_count >= 3` gets TTL = 4h (same as VkusVill cooldown — repeat offender).

`refresh_proxy_list` reads the deadlist before probing, adds node.host to cooling set. Only unknown-state or expired-quarantine hosts reach `_probe_candidates_in_parallel`.

### REL-17: Refresh throttle

Module-level `_last_refresh_ts` in `VlessProxyManager`. `ensure_pool` checks `time.time() - self._last_refresh_ts < REFRESH_MIN_INTERVAL_S` (default 60s) → skip with "refresh throttled" log. Scrapers fall through to retry later; they don't all triple-trigger the same refresh.

### REL-18: Lower water mark + rate-of-decline

- `MIN_HEALTHY = 7` → `MIN_HEALTHY = 10` (1 line).
- New `_pool_size_history: deque[tuple[ts, size]]` (max 20 entries, ~1h of samples at 3 min/cycle).
- `is_declining_fast()` returns True if `size_5_min_ago - size_now >= 3`. `ensure_pool` calls this and triggers refresh proactively even if `size >= MIN_HEALTHY`.

### REL-19: Scheduler graceful degrade

`scheduler_service.py` pre-check before each scrape:
- If pool size == 0, count consecutive-empty cycles.
- On 2nd consecutive empty cycle, **skip scrape** with exit 0, write `scheduler_pool_dead` JSONL event to `data/scheduler_events.jsonl`.
- Continue next cycle; no change to cycle cadence. Refresh daemon still runs (REL-16/17 handle that).

This prevents the current behavior where all 3 scrapers fail with exit 1, which inflates failure counters and wastes 60s+ of xvfb/Chrome startup per-scraper.

### OBS-08 (conditional)

If `bot/notifier.py` has existing admin-DM infrastructure, fold in: Telegram alert when pool size stays 0 for > 10 min. One-shot alert per incident with 30-min cooldown. Only ship if trivial (< 20 LOC); else defer to v1.25.

## Non-Goals

- **No change to upstream VLESS provider** (igareck). That's a v2+ scope discussion.
- **No change to the admitted-node reprobe daemon** (v1.21 REL-13). Still runs every 10 min through the bridge.
- **No change to xray auto-reload** (v1.21 REL-14). Still fires on admission diff.
- **No new UI surface for quarantine** — `quarantined_count` already exposed in `/api/health/deep`; that's enough for ops.

## Files Touched

| File | Change |
|---|---|
| `vless/manager.py` | Quarantine deadlist read/write, refresh throttle, rate-of-decline check, `MIN_HEALTHY` → 10 |
| `vless/quarantine.py` (new) | Deadlist load/save/expiry helpers (mirrors v1.23 `detail_events.py` pattern) |
| `scheduler_service.py` | Pre-scrape pool-dead check + `scheduler_events.jsonl` writer |
| `tests/test_vless_quarantine.py` (new) | Deadlist TTL expiry, refresh skip, throttle no-op |
| `scripts/verify_v1.24.sh` (new) | Phase 77 smoke: quarantine persists, throttle works, pool recovery ≤10 min |

## Plan Order

1. **77-01**: Core — `vless/quarantine.py` module + integrate into `vless/manager.py` (REL-16, REL-17, REL-18).
2. **77-02**: Scheduler graceful degrade (REL-19) + unit test.
3. **77-03**: `scripts/verify_v1.24.sh` + live EC2 smoke + 77-VERIFICATION.md.

## Success Criteria

1. [ ] `data/pool_quarantine.json` persists probe-failed nodes with 20-min TTL.
2. [ ] `refresh_proxy_list` skips quarantined nodes — probe count drops from ~231 to ~unknown-state only.
3. [ ] `REFRESH_MIN_INTERVAL_S = 60` throttle — second refresh within 60s is no-op.
4. [ ] `MIN_HEALTHY = 10` + rate-of-decline check triggers refresh when pool lost 3+ in 5 min.
5. [ ] Scheduler skips scrape with exit 0 + `scheduler_pool_dead` JSONL event when pool 0 for 2+ consecutive cycles.
6. [ ] Unit test `tests/test_vless_quarantine.py` covers TTL expiry / skip logic / throttle no-op / decline detection.
7. [ ] Live EC2: simulate pool death (`echo '{"quarantined_hosts":{}}' > data/pool_quarantine.json; systemctl restart saleapp-scheduler`), measure recovery via `/api/health/deep` polling. Assert p95 ≤ 10 min.
8. [ ] v1.23 + earlier regression green.

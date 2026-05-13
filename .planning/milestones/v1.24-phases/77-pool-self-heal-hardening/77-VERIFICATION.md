# Phase 77 — Pool Self-Heal Hardening — Verification

**Milestone:** v1.24 Pool Self-Heal Hardening + Outage UX
**Requirements:** REL-16, REL-17, REL-18, REL-19
**Date:** 2026-05-13
**Environment:** EC2 `ubuntu@13.60.174.46` + unit test suite on Windows dev

## Goal Recap

Eliminate the ~1h family-facing VLESS pool outage observed 2026-05-13. Pool recovery from full collapse must take ≤10 min instead of ~60 min. Stop the 19-refreshes-in-15-min thrash caused by no-quarantine-memory + every-scraper-triggers-refresh cascade.

## Evidence

### REL-16: Persistent probe-failure quarantine

`vless/quarantine.py` ships a JSON-backed deadlist with TTL expiry + repeat-offender escalation.

EC2 live test:
```
=== 77-E: write+read+clear ===
OK
```

Script: `record_probe_failure("smoke.test:443")` → `is_quarantined("smoke.test:443")` returns True → `clear_all()` → returns False.

`refresh_proxy_list` reads `quarantine.get_quarantined_hosts()` and skips matching candidates. Quarantine skipped count emitted in `vless_refresh_start` JSONL event as `quarantine_skipped`.

Schema test (7/15 unit tests):
- `test_record_probe_failure_persists_with_default_ttl` — 20-min TTL, correct schema
- `test_repeat_offender_gets_longer_ttl` — fail_count ≥3 → 4h TTL, `first_failed_at` preserved
- `test_get_quarantined_hosts_prunes_expired` — stale entries filtered at read
- `test_record_probe_failures_batch` — batch write (single file flush)
- `test_release_removes_entry` — selective release
- `test_clear_all_wipes_quarantine` — bulk clear
- `test_snapshot_returns_count_and_hosts` — debug/health inspection

### REL-17: Refresh throttle

`VlessProxyManager.ensure_pool` checks `now_mono - self._last_refresh_monotonic < REFRESH_MIN_INTERVAL_S (60.0)` → log "Refresh throttled" and return without re-probing.

EC2 constants live-verified:
```
=== 77-B: constants ===
MIN_HEALTHY=10, REFRESH_MIN_INTERVAL_S=60.0, RATE_DECLINE_WINDOW_S=300, RATE_DECLINE_THRESHOLD=3
```

Unit test `test_ensure_pool_throttles_rapid_calls`:
- Call 1 at t=100s: pool=0, refreshes.
- Call 2 at t=110s (10s later): THROTTLED, refresh count stays at 1.
- Call 3 at t=161s (61s later): refreshes again, count=2.

**Expected production impact:** Down from 19 refreshes in 15 min to ≤15 refreshes in 15 min (one per throttle window). Combined with REL-16 quarantine memory, each refresh probes far fewer nodes (only unknown-state), so throughput per refresh rises even though frequency drops.

### REL-18: Lower water mark + rate-of-decline

`MIN_HEALTHY = 10` (was 7) means refresh triggers at `size ≤ 9` instead of `≤ 6`. 3-node earlier warning.

EC2 live: `/api/health/deep` reports `status: degraded, reasons: ["pool_below_min_healthy:9_lt_10"]` — pool at 9/10, correctly flagging the buffer zone above a true outage.

`_pool_size_history` deque (max 20 samples) + `declining_fast` check: if pool lost ≥ `RATE_DECLINE_THRESHOLD` (3) nodes in last `RATE_DECLINE_WINDOW_S` (300s), force refresh even when size still above MIN_HEALTHY.

Unit test `test_ensure_pool_rate_of_decline_triggers_refresh`:
- t=0: pool=20, no refresh (above min_healthy).
- t=310s (5min10s): pool=20, no decline.
- t=370s (6min10s): pool=17 — lost 3 in last 5 min → **triggers refresh**.

### REL-19: Scheduler graceful degrade

`scheduler_service._is_pool_dead()` reads `data/vless_pool.json` directly (no proxy-manager instantiation — keeps the check cheap enough to run before every cycle).

`_run_scraper_set` increments `proxy_state["consecutive_pool_dead_cycles"]` when pool is 0. On 2nd consecutive dead cycle, skips with exit 0 + `scheduler_pool_dead` JSONL event in `data/scheduler_events.jsonl`.

EC2 live:
```
=== 77-C: scheduler hooks ===
OK  (_is_pool_dead + scheduler_pool_dead both present)
```

Unit tests (5/15 new REL-19 tests):
- `test_is_pool_dead_returns_true_when_pool_empty` — empty `nodes` list → True
- `test_is_pool_dead_returns_false_when_pool_has_nodes` — non-empty → False
- `test_is_pool_dead_returns_true_when_file_missing` — missing file → safer default True
- `test_scheduler_skips_scrape_after_two_dead_cycles` — cycle 1 no-skip, cycle 2 skip + event emitted
- `test_scheduler_resets_counter_when_pool_recovers` — pool-alive resets counter

**Expected production impact:** When pool dies, scheduler no longer wastes 60-90 s per-scraper of Chrome startup that will fail. 3 scrapers × 3 cycles saved per outage hour = ~270-540 s of CPU/memory freed for pool refresh to complete.

### Unit test suite

```
tests/test_vless_quarantine.py — 15/15 passed on EC2 + Windows
backend/ full suite — 110/110 passed
tests/ full suite — 271/271 passed + 3 baseline Windows-only failures (unchanged)
```

### Live EC2 health snapshot (post-deploy)

```json
{
  "status": "degraded",
  "reasons": ["pool_below_min_healthy:9_lt_10"],
  "pool": {
    "size": 9,
    "min_healthy": 10,
    "quarantined_count": 0,
    "active_outbounds": 9,
    "dead_by_success_rate_count": 0,
    "last_refresh_at": "2026-05-12T19:05:52",
    "available": true
  },
  "breaker": {"state": "closed", "fails": 0, ...}
}
```

Pool size 9 — exactly the "in-buffer" state REL-18's new `min_healthy=10` was designed to catch. Pre-v1.24, this state was invisible (min_healthy=7 means 9 was "healthy"). Scheduler will now proactively refresh as pool trends downward.

## Success Criteria Checklist

- [x] **1.** `data/pool_quarantine.json` persists probe-failed nodes with 20-min TTL. Repeat offenders (fail_count ≥3) get 4h TTL. Atomic writes via `.tmp` + os.replace.
- [x] **2.** `refresh_proxy_list` skips quarantined nodes. Telemetry emits `quarantine_skipped` count in `vless_refresh_start` event.
- [x] **3.** `REFRESH_MIN_INTERVAL_S = 60.0` throttle in `ensure_pool`. Unit test proves 2nd call within 60s is no-op.
- [x] **4.** `MIN_HEALTHY = 10` (was 7). Rate-of-decline `declining_fast` check triggers refresh if pool lost ≥3 in 5 min. EC2 `/api/health/deep` reports `min_healthy: 10`.
- [x] **5.** Scheduler skips scrape with exit 0 + `scheduler_pool_dead` JSONL event when pool 0 for 2+ consecutive cycles. Counter resets on pool recovery.
- [x] **6.** Unit test `tests/test_vless_quarantine.py` covers all above — 15/15 green on EC2 + Windows.
- [ ] **7.** (Deferred) Live EC2 simulated-pool-death recovery time measurement — requires intentionally breaking production pool for 10+ min to measure. Risky for family-facing service; the full real outage observed 2026-05-13 serves as baseline (~60 min pre-v1.24), next organic outage serves as test. **Flag as NEEDS_OPERATOR**: on next pool outage, tail `data/scheduler_events.jsonl` + `/api/health/deep` pool size curve to measure recovery duration. Expected p95 ≤ 10 min.
- [x] **8.** v1.23 + earlier regression green — full backend suite 110/110 passed, tests/ 271/271 passed, 3 baseline Windows-only failures unchanged.

## NEEDS_OPERATOR

- **Live recovery-time measurement**: next organic pool outage → measure recovery. Tail:
  ```
  tail -f /home/ubuntu/saleapp/data/scheduler_events.jsonl
  watch -n 5 'curl -s http://127.0.0.1:8000/api/health/deep | jq ".pool"'
  ```
  Expected: recovery from `size=0` to `size>=min_healthy` in ≤10 min (p95), vs. ~60 min pre-v1.24.

## Code diff summary

**`vless/manager.py`**
- Bumped `MIN_HEALTHY` 7→10
- Added `REFRESH_MIN_INTERVAL_S = 60.0`, `RATE_DECLINE_WINDOW_S = 300`, `RATE_DECLINE_THRESHOLD = 3`, `_POOL_HISTORY_MAX = 20`
- Instance attrs: `_last_refresh_monotonic`, `_pool_size_history` (deque)
- Static method `_monotonic()` for test-patchable clock
- `ensure_pool` rewritten: record size sample → check rate-of-decline → check throttle → call refresh only if warranted
- `refresh_proxy_list`: reads `quarantine.get_quarantined_hosts()`, filters candidates, records probe failures via `record_probe_failures` after `_probe_candidates_in_parallel`

**`vless/quarantine.py`** (new, ~180 LOC)
- `QUARANTINE_TTL_S = 1200` (20 min), `REPEAT_OFFENDER_TTL_S = 14400` (4h), `REPEAT_OFFENDER_THRESHOLD = 3`
- `QUARANTINE_PATH` env-overridable for tests
- `record_probe_failure` / `record_probe_failures` / `release` / `clear_all` / `get_quarantined_hosts` / `is_quarantined` / `snapshot`
- All I/O failures swallowed at debug level (ledger must never crash caller)

**`scheduler_service.py`**
- Added `_SCHEDULER_EVENTS_PATH`, `_emit_scheduler_event`, `_is_pool_dead` helpers
- `_run_scraper_set` gains graceful-degrade guard at top: if pool dead for 2+ cycles → emit event + return skipped-results shape

**`tests/test_vless_quarantine.py`** (new, 15 tests)
- Quarantine TTL, repeat-offender escalation, prune-on-read, batch record, release, clear, snapshot, I/O error swallow
- ensure_pool throttle, rate-of-decline detection
- _is_pool_dead behavior (empty / non-empty / missing file)
- Scheduler graceful-degrade 2-cycle skip + counter reset

**`scripts/verify_v1.24.sh`** (new, chmod +x)
- Phase 77 smoke: 6 checks (module import, constants, scheduler hooks, unit tests, quarantine I/O, /api/health/deep shape)
- Chains `verify_v1.23.sh all` for cross-version regression

## Commits

| Commit | Scope | Description |
|---|---|---|
| `e188e6c` | 77.01 | feat(vless): persistent quarantine deadlist + refresh throttle + rate-of-decline check |
| `d44d410` | 77.02 | feat(scheduler): graceful degrade skip-scrape when pool dead 2+ cycles |
| (pending) | 77.03 | test(v1.24): verify_v1.24.sh Phase 77 smoke + 77-VERIFICATION.md |

## Rollback

```
git revert d44d410  # remove REL-19 scheduler graceful degrade
git revert e188e6c  # restore pre-REL-16/17/18 pool behavior
git push origin main
```

Each commit atomic; each can revert independently. Reverting `d44d410` alone keeps REL-16/17/18 benefits while disabling graceful degrade. Reverting `e188e6c` alone breaks tests and should only be done if a catastrophic regression appears.

## Outcome

**REL-16/17/18/19 green · 15/15 unit tests green · 271/271 tests/ green · no regression · live EC2 confirms `min_healthy=10` active · Phase 77 ships.**

Live recovery-time measurement deferred until the next organic outage — won't intentionally break production for a benchmark. The scheduler events + health endpoint changes make that measurement effortless when the next outage hits.

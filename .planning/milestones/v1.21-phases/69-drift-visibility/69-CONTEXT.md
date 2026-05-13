# Phase 69 — Drift Visibility — `/api/health/deep` + `/admin/status` + proxy_events — Context

**Milestone:** v1.21 VLESS Pool Self-Healing & Reload Pipeline
**Phase number:** 69
**Phase slug:** drift-visibility
**Date captured:** 2026-05-12
**Requirements covered:** OBS-06, OBS-07 (completion) + continuing OPS-12/13/14

---

## Domain

Phase 67 fixed admission staleness. Phase 68 fixed config-reload blindness. Phase 69 closes the remaining failure mode from the 2026-05-06 → 05-10 outage: **operators had no signal that the pool and the running xray were out of sync.** Pool snapshot showed `size=16, quarantined=7` — looked healthy. External uptime monitors hitting `/api/health/deep` saw `status=healthy` because all v1.19 criteria passed (pool >= MIN_HEALTHY, breaker closed, cycle fresh, xray listening on 10808). Nothing surfaced "the outbounds the running xray is using aren't the outbounds the pool thinks are admitted."

Phase 68 emits one `pool_refresh_complete` event per refresh with `xray_restart_triggered` + `added_hosts` + `removed_hosts` + `restart_outcome`. Phase 69 surfaces the *current* drift (not just per-refresh deltas) on the health endpoint so external monitors catch it in minutes, and mirrors the block to the admin dashboard.

"Drift" is defined as:

```
drift_count = |admitted_hosts △ active_outbounds|
            = |admitted_hosts - active_outbounds| + |active_outbounds - admitted_hosts|
```

where `admitted_hosts` is the host set in `data/vless_pool.json` and `active_outbounds` is the host set the running xray config currently references (same source of truth as `_extract_running_hosts` from Phase 68).

---

## SPEC Lock

LOCKED from REQUIREMENTS.md OBS-06 / OBS-07:

### OBS-06 — `/api/health/deep` xray_drift block

- New optional top-level key `xray_drift` in the snapshot returned by `_build_reliability_snapshot` (and thus by both `/api/health/deep` and `/admin/status.reliability`).
- Shape:
  ```json
  "xray_drift": {
      "admitted_hosts": 14,
      "active_outbounds": 14,
      "drift_count": 0,
      "drifted_hosts": [],
      "first_seen_at": null
  }
  ```
  or when drift is present:
  ```json
  "xray_drift": {
      "admitted_hosts": 14,
      "active_outbounds": 12,
      "drift_count": 3,
      "drifted_hosts": ["1.2.3.4", "5.6.7.8", "9.10.11.12"],
      "first_seen_at": "2026-05-12T19:30:00"
  }
  ```
- Block absent entirely when pool snapshot is unavailable (same no-ledger fallback pattern as the v1.20 `cart_add` block).
- Threshold logic (adds to existing `reasons[]` + status mapping):
  - `drift_count > 0` AND drift persists > 5 min → reason `xray_stale_config:{N}_nodes_drifted` (→ `degraded` severity).
  - `drift_count > 0` AND `last_cycle_age_s > 10 * 60` → same reason, but counts toward `unhealthy` severity (n_failed ≥ 3 path already exists).
- First-seen persistence: in-process dict `_DRIFT_FIRST_SEEN: dict[frozenset[str], float]` keyed by the drifted-host set (not host-by-host — drift persists only while the exact same set is drifted; set change resets the clock). Timestamp is `time.monotonic()` for freshness math, timestamp-as-ISO exposed to UI is `datetime.now().isoformat(timespec="seconds")` captured at first-seen.

### OBS-07 — `pool_refresh_complete` completion

Phase 68 already emits the event with `admitted_count`, `admitted_hosts_before`, `admitted_hosts_after`, `added_hosts`, `removed_hosts`, `xray_restart_triggered`, `restart_duration_ms`, `restart_outcome`, `restart_stderr_tail`. Phase 69 only ADDS `success_rate_drops: list[str]` (hosts demoted to dead by REL-15 during this refresh cycle — "the list of hosts that went from alive→dead in the admission loop just completed"). No other schema change.

### Admin dashboard mirror

`/admin/status` already calls `_build_reliability_snapshot()` and surfaces it under `reliability`. The new `xray_drift` block flows through automatically — no admin.html wiring needed in this phase. A future v1.22 phase can add a UI card if desired.

---

## Decisions

### D1. Why drift tracking lives in backend/main.py, not VlessProxyManager

`_extract_running_hosts` is a VlessProxyManager helper. But drift age + first_seen_at are a *monitor* concern, not a pool-manager concern. Keeping the threshold logic in `backend/main.py` next to the other reliability criteria keeps `VlessProxyManager` focused on pool ownership and makes the new behavior testable against a mocked `_pool_snapshot_for_health` + `_extract_running_hosts_for_health` without spinning up a full manager.

### D2. Drift comparison at snapshot time, not at refresh time

Phase 68 *reacts* to admission-diff at refresh time by calling systemctl. Phase 69 *reports* drift at snapshot time: whenever `/api/health/deep` is hit. This answers two different questions:
  - "Did the admission change fire a restart?" (refresh-time — Phase 68 event)
  - "Is the pool in sync with the running xray *right now*?" (snapshot-time — Phase 69 block)

The two can disagree: if Phase 68 throttled the restart, the admission change happened but xray is still running old config → snapshot-time drift correctly flags it, refresh-time event correctly says `restart_outcome: "throttled"`.

### D3. `drifted_hosts` is the symmetric difference sorted

`list(sorted(admitted ^ active_outbounds))`. Stable order for test assertions and admin display.

### D4. First-seen key is the drifted-set, not "any drift"

If drift appears for set A at t=0, resolves at t=2min, re-appears for set B at t=10min, the new first_seen_at is t=10min (not t=0min). This matches operator intuition: "this drift is 30s old, even though there was a different drift earlier today."

In practice the dict has at most one entry at a time (current drifted set). We still prune entries whose set is no longer drifted to avoid stale memory.

### D5. Drift block absent when pool unavailable

`_pool_snapshot_for_health` returns `{"available": False}` on startup before any pool refresh. In that window we can't compute drift (admitted count unknown) — same pattern as the v1.20 cart_add block, which is absent until there's at least one attempt.

### D6. `success_rate_drops` computed inside `refresh_proxy_list`

Before writing new pool state, iterate existing nodes and snapshot their current `_is_node_dead(n)` state. After pool rewrite, iterate again and emit the list of hosts that went from not-dead → dead. Minor but correct.

### D7. Threshold constants

- `_DEEP_DRIFT_DEGRADED_S = 5 * 60` (5 min — REL-14 spec)
- `_DEEP_DRIFT_UNHEALTHY_CYCLE_AGE_S = 10 * 60` (10 min — REL-14 spec)

Named with the `_DEEP_` prefix matching existing thresholds.

---

## Locked Defaults

- Drift block key: `"xray_drift"` (top-level in snapshot)
- Drift field shape: `{admitted_hosts, active_outbounds, drift_count, drifted_hosts, first_seen_at}`
- Reason format: `xray_stale_config:{drift_count}_nodes_drifted`
- `_DEEP_DRIFT_DEGRADED_S = 300` (5 min)
- `_DEEP_DRIFT_UNHEALTHY_CYCLE_AGE_S = 600` (10 min)
- `_DRIFT_FIRST_SEEN: dict[frozenset[str], float]` — in-memory only

---

## Files Modified

- `backend/main.py`:
  - New constants `_DEEP_DRIFT_DEGRADED_S`, `_DEEP_DRIFT_UNHEALTHY_CYCLE_AGE_S`, `_DRIFT_FIRST_SEEN`.
  - New helper `_extract_running_xray_hosts_for_health() -> set[str] | None` — mirrors VlessProxyManager._extract_running_hosts but reads the same `bin/xray/configs/active.json` path the backend uses. Returns `None` on missing/malformed (distinct from `set()` which means "file present, no VLESS outbounds").
  - New helper `_compute_xray_drift_block(pool: dict) -> tuple[dict | None, str | None, bool]` — returns `(block, reason, is_critical)` where `reason` is non-None only when drift has persisted > 5 min, and `is_critical` is True when `drift + stale_cycle` combo hits.
  - `_build_reliability_snapshot`: call `_compute_xray_drift_block(pool)`, attach block if non-None, append reason if returned, bump severity if critical (inject into the existing `critical = {...}` set or equivalent).
- `vless/manager.py`:
  - `refresh_proxy_list` — compute `success_rate_drops` (see D6), add to `pool_refresh_complete` payload.
- `tests/test_xray_drift_health.py` (NEW, 7 tests):
  - `test_xray_drift_block_absent_when_pool_unavailable`
  - `test_xray_drift_block_computed_when_sets_match`
  - `test_xray_drift_block_reports_drift_count`
  - `test_xray_drift_reason_absent_within_grace`
  - `test_xray_drift_reason_added_after_5_min`
  - `test_xray_drift_unhealthy_when_also_stale_cycle`
  - `test_xray_drift_first_seen_resets_on_set_change`
- `tests/test_xray_reload.py` (EXTEND, +1 test):
  - `test_pool_refresh_complete_includes_success_rate_drops`
- `scripts/verify_v1.21.sh` — append Phase 69 block with 69-A/B/C/D checks.
- `.planning/phases/69-drift-visibility/69-VERIFICATION.md` — runbook.

---

## Verification

- Local: 7 new tests in `test_xray_drift_health.py` + 1 extension test green; full suite 349+ passed + 3 baseline.
- NEEDS_OPERATOR (69-VERIFICATION.md):
  - External `curl https://vkusvillsale.vercel.app/api/health/deep | jq .xray_drift` returns the block when pool+xray are in sync.
  - Inject drift: hand-edit `data/vless_pool.json` to drop a host, skip the scheduler-triggered restart for 6 min → endpoint returns 503 with `xray_stale_config:1_nodes_drifted` and `xray_drift.drift_count=1`.
  - Manual `sudo systemctl reload-or-restart saleapp-xray` → drift clears, endpoint returns 200 within 30s.
  - v1.20 + v1.19 regression green.

---

## Phase Boundary

**Ships:** `/api/health/deep` + `/admin/status.reliability` `xray_drift` block with 5-min degraded / 10-min unhealthy thresholds, `pool_refresh_complete` event schema completion via `success_rate_drops`, 8 unit tests, 4 smoke checks.

**Does NOT ship:**
- admin.html UI card surfacing drift (deferred to v1.22 UX debt milestone)
- Telegram alerts on drift (v2 REL-FUT-05)
- Drift rate-of-change panel / historical drift trace (future observability milestone)

**Acceptance gate:** 8/8 unit tests green + 4/4 smoke on EC2 + external curl proves drift block surfaces when injected and clears when resolved.

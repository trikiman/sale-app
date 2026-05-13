# Phase 67 — Admitted-Node Self-Healing Loop — Context

**Milestone:** v1.21 VLESS Pool Self-Healing & Reload Pipeline
**Phase number:** 67
**Phase slug:** admitted-node-self-healing-loop
**Date captured:** 2026-05-12
**Requirements covered:** REL-13, REL-15 + continuing OPS-12/13/14

---

## Domain

The 4-day VLESS outage 2026-05-06 → 05-10 had two root causes; Phase 67 addresses the first: **admitted nodes never re-probed under production conditions**. A node passes `_probe_vkusvill` at admission (authenticated HEAD against vkusvill.ru) and is written into `data/vless_pool.json`. Minutes or hours later, VkusVill's anti-bot silently blocks that IP. Observatory probes through the dead outbound also fail, so the balancer has no rotation signal. Pool shows `size=16, quarantined=7` (looks healthy), but end-to-end reachability is 0%.

Phase 67 introduces:
1. **Periodic re-probe loop** — daemon thread in `scheduler_service.py` that iterates each admitted node every ≤10 min, re-runs `_probe_vkusvill` through the running bridge (not a fresh xray subprocess), and routes failures into the existing 4h VkusVill cooldown.
2. **Per-node production success_rate** — `VlessProxyManager` pool entries gain `last_success_at` and a 100-sample sliding `success_rate` updated on every real cart-add, scrape call, and re-probe. Nodes with `success_rate < 0.1` (and sample count ≥ 20) are excluded from active outbounds on next refresh even if observatory still reports them alive.

---

## SPEC Lock (from REQUIREMENTS.md REL-13/15)

LOCKED — planner must NOT re-litigate:

- **Re-probe cadence:** 10 minutes. Module-level constant `REPROBE_INTERVAL_S = 600.0`. Same deadline-based loop pattern as `keepalive.warmup.start_warmup_loop` so the scheduler watchdog + stop_event protocol is identical.
- **Re-probe target:** every admitted node in `VlessProxyManager._pool["nodes"]` (NOT cooldown'd nodes — those are already out).
- **Re-probe endpoint:** `_probe_vkusvill(proxy=None)` through the running bridge (proxy=None means "use the local xray bridge" since every call routes through 127.0.0.1:10808). DO NOT spawn a fresh xray subprocess per probe — that's admission-time behavior, not steady-state.
- **Re-probe timeout:** same `PROBE_TIMEOUT=8` used by admission. Consistency > tuning.
- **Failure handling:** calling `mark_vkusvill_blocked(host, reason="reprobe_fail")` — reuses existing 4h cooldown + `_remove_host_and_restart` machinery. No new cooldown type.
- **Refresh gate:** re-probe loop does NOT call `refresh_proxy_list` directly. It only marks nodes blocked. When `pool_count() < MIN_HEALTHY` after marking, the NEXT call to `ensure_pool()` (already runs on every `get_working_proxy`) triggers refresh naturally.
- **success_rate implementation:** pool node entries gain two new fields: `success_rate_samples: list[bool]` (max 100 entries, FIFO) and `last_success_at: float | None`. Updated via new public method `VlessProxyManager.record_outcome(host, success: bool)`. Call sites: `cart/vkusvill_api.py::add` on success/fail, `scrape_green/red/yellow` detail-fetch, the new re-probe loop. Lazy computation: `success_rate()` method returns `sum(samples)/len(samples)` only when `len(samples) >= 20`; below that returns `None` (unknown).
- **Dead-node exclusion:** `pool_snapshot()` + `get_working_proxy()` + `refresh_proxy_list` filter out entries where `success_rate() is not None and < 0.1`. Integration point: new private helper `_is_node_dead(entry) -> bool` called from those three sites.
- **No persistence:** `success_rate_samples` and `last_success_at` live in memory only. On process restart the sliding window reboots from zero. Acceptable because scheduler restarts are rare and the re-probe loop will repopulate within 10 min.
- **No schema change to `vless_pool.json`:** only in-memory additions. The on-disk pool stays backward-compatible with v1.19/v1.20.
- **Daemon wiring:** spawned from `scheduler_service.main()` near the existing `keepalive_thread` block. Name: `scheduler-reprobe`. Respects the same `stop_event` pattern.
- **Smoke gate:** `scripts/verify_v1.21.sh` gains 67-A (module imports), 67-B (REPROBE_INTERVAL_S == 600), 67-C (record_outcome + success_rate roundtrip), 67-D (induced-failure end-to-end: block vkusvill via hosts for 60s → re-probe detects → pool drops below MIN_HEALTHY within 2 min).
- **OPS-12 cross-version:** `verify_v1.21.sh all` chains `verify_v1.20.sh all` + `verify_v1.19.sh all` at the end. Both must stay green.
- **OPS-13 end-to-end outage reproduction:** 67-D covers REL-13 half. REL-14 half lands in Phase 68.
- **OPS-14 rollback rehearsal:** mandatory before merge; single-commit revert of the daemon + manager changes leaves backend green.

---

## Decisions

### D1. Daemon in scheduler_service, not in manager

Re-probe is scheduler-owned, same as warmup. Putting it in `VlessProxyManager` couples pool lifecycle to I/O timing in ways that break the existing test surface. Scheduler spawns, manager exposes `iter_admitted_hosts()` + `record_outcome()`.

### D2. Don't trigger refresh from re-probe

Re-probe marks nodes blocked via `mark_vkusvill_blocked`, which already calls `_remove_host_and_restart` synchronously. When pool drops below MIN_HEALTHY, the next `get_working_proxy()` call triggers `ensure_pool()` which triggers `refresh_proxy_list()`. That path is already well-tested. No reason to duplicate the refresh trigger from a second site.

### D3. success_rate is advisory, not blocking

If `len(samples) < 20`, `success_rate()` returns `None` ("unknown"). We don't exclude nodes with insufficient samples — otherwise every fresh admission looks dead. Exclusion threshold: `success_rate is not None AND < 0.1 AND len(samples) >= 20`. Conservative.

### D4. Record outcomes at 3 call sites only

- `cart/vkusvill_api.py::add` — success/fail per cart-add (end-user truth).
- `scrape_green/red/yellow.py` — success/fail per detail-fetch batch (scraper truth).
- Re-probe loop itself — direct probe truth.

NOT adding to: image proxy (too high-volume, would dominate the sample), product-details endpoint (same issue), nodriver login (one-shot, rare).

### D5. host resolution in record_outcome

When a caller hits `127.0.0.1:10808` they don't know which real VLESS node xray routed to. So `record_outcome(host, success)` takes the host parameter explicitly, and callers that CAN know the host (scrapers that inspect xray's active outbounds) pass it. Callers that CAN'T (cart/vkusvill_api) pass `host=None` → record against the pool's current head-of-list (matches `mark_current_node_blocked`'s existing heuristic).

---

## Locked Defaults

- `REPROBE_INTERVAL_S = 600.0` (10 min)
- `REPROBE_BOOT_GRACE_S = 120.0` (wait 2 min after scheduler start before first re-probe cycle)
- `SUCCESS_RATE_WINDOW = 100` (samples)
- `SUCCESS_RATE_MIN_SAMPLES = 20`
- `SUCCESS_RATE_DEAD_THRESHOLD = 0.1`

---

## Files Modified

- `vless/manager.py`:
  - `VlessProxyManager.__init__`: initialize `self._outcomes: dict[str, list[bool]]` (per-host deque of last 100) and `self._last_success_at: dict[str, float]`.
  - New public `iter_admitted_hosts() -> list[str]` — returns list of `host` strings from current pool (lock-safe).
  - New public `record_outcome(host: str | None, success: bool) -> None` — appends to the FIFO sample list, bounds to 100.
  - New public `success_rate(host: str) -> float | None` — returns rate or None if < 20 samples.
  - Private `_is_node_dead(entry: dict) -> bool` — consults success_rate for exclusion.
  - `pool_snapshot()`: add `dead_by_success_rate_count` field; subtract dead nodes from `active_outbounds`.
  - `get_working_proxy()`: existing fallthrough; if all live nodes are "dead by success_rate", fall back to normal ordering (fail-safe).
  - `refresh_proxy_list()`: before rebuilding xray config, exclude dead nodes (same as cooldown'd).
- `keepalive/reprobe.py` (NEW, ~150 LOC):
  - `start_reprobe_loop(stop_event, proxy_manager)` daemon entry.
  - `_run_cycle(proxy_manager, stop_event)` — iterates admitted hosts, calls `_probe_vkusvill` through bridge, records outcome, routes failures to `mark_vkusvill_blocked`.
  - Emits JSONL events to `data/proxy_events.jsonl` (type `reprobe_cycle_complete` with counts).
  - Respects `stop_event.wait(REPROBE_INTERVAL_S)` for cancellation.
- `scheduler_service.py`:
  - Import `start_reprobe_loop` from `keepalive.reprobe`.
  - Spawn daemon thread `scheduler-reprobe` after `keepalive_thread` startup.
  - Add `_reprobe_stop_event` to atexit cleanup.
- `cart/vkusvill_api.py::add`:
  - After `basket_add.php` response, call `_proxy_manager.record_outcome(None, success=True/False)`. host=None uses head-of-list heuristic.
- `scrape_green.py` + `scrape_red.py` + `scrape_yellow.py`:
  - After detail-fetch batch, call `_proxy_manager.record_outcome(None, success)` — same heuristic.
- `tests/test_reprobe_loop.py` (NEW, 6 tests):
  - `test_record_outcome_fifo_window`: bound at 100 samples.
  - `test_success_rate_unknown_below_20_samples`: returns None.
  - `test_success_rate_computed_above_20_samples`: 5 success + 15 fail = 0.25.
  - `test_dead_node_excluded_from_active_outbounds`: node with rate < 0.1 dropped from pool_snapshot.
  - `test_reprobe_cycle_marks_failed_host_cooldown`: mock `_probe_vkusvill` → False, assert `mark_vkusvill_blocked` called.
  - `test_reprobe_boot_grace_respected`: cycle 1 fires after 120s, not immediately.
- `scripts/verify_v1.21.sh` (NEW, skeleton + Phase 67 block):
  - 67-A imports clean on EC2
  - 67-B REPROBE_INTERVAL_S == 600.0
  - 67-C record_outcome + success_rate unit test green
  - 67-D induced-failure end-to-end (hosts-block for 60s → pool drops within 2 min)
- `.planning/phases/67-admitted-node-self-healing-loop/67-VERIFICATION.md` (NEW, NEEDS_OPERATOR items)

---

## Verification

- Local: 6 new pytest cases pass, full suite green (no regression), `bash -n scripts/verify_v1.21.sh` exit 0.
- NEEDS_OPERATOR (67-VERIFICATION.md):
  - EC2 deploy + scheduler restart to pick up daemon.
  - Induce hosts-override block for 60s: `echo "0.0.0.0 vkusvill.ru" | sudo tee -a /etc/hosts`; wait for re-probe to detect; verify `data/proxy_events.jsonl` has `reprobe_cycle_complete` events with failures; verify `pool_snapshot().size` decreased.
  - Restore `/etc/hosts`; verify pool refresh re-admits within 2 min.
  - Rollback rehearsal.

---

## Phase Boundary

**Ships:** 10-min re-probe daemon + success_rate tracking + dead-node exclusion + 6 tests + 4 smoke checks.

**Does NOT ship:** xray auto-reload on admission change (Phase 68), drift visibility in `/api/health/deep` (Phase 69), Telegram alerting (v2).

**Acceptance gate:** 6/6 tests green + full suite no regression + bash -n clean + 67-D smoke path reproducible on EC2.

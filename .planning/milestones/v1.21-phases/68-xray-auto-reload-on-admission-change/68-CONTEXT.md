# Phase 68 — xray Auto-Reload on Admission Change — Context

**Milestone:** v1.21 VLESS Pool Self-Healing & Reload Pipeline
**Phase number:** 68
**Phase slug:** xray-auto-reload-on-admission-change
**Date captured:** 2026-05-12
**Requirements covered:** REL-14 + continuing OPS-12/13/14

---

## Domain

The 4-day outage 2026-05-06 → 05-10 had a second root cause (distinct from Phase 67's silent admission staleness): **`refresh_proxy_list` rewrites `bin/xray/configs/active.json` but the running xray process never re-reads it.** Every hour the pool pipeline fetched upstream nodes, probed them, admitted survivors, and wrote the new config. The systemd-managed `saleapp-xray.service` (PID set once at systemd boot 2026-05-05 15:27 MSK) read its config ONCE on startup and stayed pinned to outbounds that had long been removed from the pool file.

Phase 67 fixed the admitted-set staleness so the pool JSON now represents reality. Phase 68 closes the loop: when `refresh_proxy_list` admits a host set whose `host` list differs from the currently-running xray config, the scheduler calls `sudo systemctl reload-or-restart saleapp-xray`.

Manual fix rehearsed on 2026-05-10: after restarting xray + whitelisting 8 probed-good nodes, bridge → `vkusvill.ru` probe went from HTTP 000 (15s timeout) to HTTP 200 (1.4-5s) immediately, and a full scraper cycle completed within 2 minutes. Phase 68 automates that restart.

---

## SPEC Lock (from REQUIREMENTS.md REL-14)

LOCKED — planner must NOT re-litigate:

- **Reload trigger:** `VlessProxyManager.refresh_proxy_list` — after the new pool is persisted and the xray config regenerated, compare the new admitted host set vs the running xray config's outbound host set. If different, call `sudo systemctl reload-or-restart saleapp-xray`.
- **No-op when set unchanged:** if newly-admitted hosts ⊆ running-config hosts AND running-config hosts ⊆ newly-admitted hosts, skip the restart. No restart churn.
- **Throttle:** ≤ 1 restart per 90 seconds, tracked via in-memory `self._last_xray_restart_monotonic`. When a refresh would fire a restart but the window is still open, log and defer — the next refresh's admission-set check will trigger it if the difference persists.
- **Sudoers:** deploy adds a passwordless sudoers entry for `ubuntu` on `saleapp-xray.service` ONLY (not `ALL`, not `systemctl restart *`). Entry format: `ubuntu ALL=(root) NOPASSWD: /bin/systemctl reload-or-restart saleapp-xray, /bin/systemctl restart saleapp-xray`. Dropped into `/etc/sudoers.d/saleapp-xray-reload` (660, `visudo -c` validated). Documented in 68-VERIFICATION.md as manual deploy step.
- **Restart method:** `reload-or-restart` (graceful where possible, falls back to restart). NOT `restart` unconditionally — if xray ever grows a `ReloadExec=` it'll reuse it. `subprocess.run(["sudo", "systemctl", "reload-or-restart", "saleapp-xray"], timeout=30, capture_output=True)`.
- **Error handling:** if the subprocess exits non-zero or times out, emit `xray_restart_failed` JSONL event with stderr tail (first 500 chars), leave pool state unchanged, DO NOT retry immediately. Next refresh retries naturally.
- **Observability:** the existing `pool_refresh_complete` JSONL event is extended with: `xray_restart_triggered: bool`, `restart_duration_ms: int | None` (None when not triggered), `restart_outcome: str` (`ok` | `throttled` | `unchanged` | `failed`), `admitted_hosts_before: list[str]` (from the ~running config), `admitted_hosts_after: list[str]` (from the new pool), `added_hosts: list[str]`, `removed_hosts: list[str]`. Events schema change is additive-only; existing consumers (admin/status, post-mortem tools) ignore unknown keys.
- **In-process xray lifecycle is OUT OF SCOPE** (per v1.15 D7). Systemd remains the lifecycle owner. If `self._xray is not None` (legacy test path where a dev manager owns its own subprocess), skip systemctl entirely and fall back to `self._xray.stop() + self._xray.start()` — matches pre-68 behavior for unit tests.
- **Test strategy:** unit tests use a mock for `subprocess.run`, assert argv shape + throttle + no-op branches. No real systemd calls in tests. Integration test runs on EC2 via the smoke script.
- **Smoke gate:** `scripts/verify_v1.21.sh` Phase 68 block: 68-A (admission_set diff function importable + pure), 68-B (throttle constant locked at 90s), 68-C (sudoers entry file exists on EC2), 68-D (last pool_refresh_complete event has `xray_restart_triggered` key — shape check, no wall-clock asserts).

---

## Decisions

### D1. Why `reload-or-restart` vs plain `restart`

xray v25.x ships without a documented `ReloadExec=` in systemd unit files but the binary DOES support SIGUSR1 as "reload config" in some versions. `reload-or-restart` is systemd-policy-safe: if the unit supports reload, use it; if not, fall back to restart. Either way the running config picks up changes. Plain `restart` would force a ~2-3s downtime even when reload would work.

### D2. In-memory throttle (not persisted)

Persisting the last-restart timestamp to disk adds a failure mode (corrupt JSON) and a race (multiple scheduler processes during deploy). In-memory is correct because:
- Scheduler is single-process (systemd unit, no workers).
- Scheduler restart itself implicitly resets the throttle — a fresh boot SHOULD be allowed to restart xray immediately.
- 90s is short enough that even if we miss a genuine reload opportunity, the next refresh (≤ 1 hour away, usually ≤ 10 min with pool-below-MIN-healthy) will pick it up.

### D3. Compare sets, not lists

"Same host list in different order" must NOT trigger a restart. `set(new_hosts) == set(old_hosts)` is the right check. Port is part of the node but NOT part of the set comparison — hosts are stable identifiers, ports rarely change and a port-only change is rare enough to ignore (next scheduled refresh picks it up if it matters).

### D4. Running-config host set extraction

Read `bin/xray/configs/active.json`, iterate `outbounds`, extract `settings.vnext[].address` for VLESS outbounds. Skip the `direct` and `dns` outbounds. If the config file is missing or malformed, treat running-config as empty set → any admission fires the restart (recovery path on first deploy).

### D5. Call site

Inside `refresh_proxy_list` RIGHT AFTER `_write_xray_config_from_pool` (or whichever existing helper writes the config). Before returning to the caller. Idempotent — if the caller invokes refresh twice in a row with identical output, the second one no-ops via D2 throttle or D3 set comparison.

### D6. Skip on Windows

`subprocess.run(["sudo", "systemctl", ...])` on Windows will fail noisily. Detect via `sys.platform == "win32"` and skip with an info log. Unit tests run on Windows for the dev box; integration via `scripts/verify_v1.21.sh` runs on EC2 only.

---

## Locked Defaults

- `XRAY_RESTART_THROTTLE_S = 90.0`
- `XRAY_RESTART_TIMEOUT_S = 30.0`
- `SYSTEMCTL_ARGS = ["sudo", "systemctl", "reload-or-restart", "saleapp-xray"]`
- Sudoers path: `/etc/sudoers.d/saleapp-xray-reload` (mode 0440)
- Sudoers content: `ubuntu ALL=(root) NOPASSWD: /bin/systemctl reload-or-restart saleapp-xray, /bin/systemctl restart saleapp-xray`

---

## Files Modified

- `vless/manager.py`:
  - Add 3 constants: `XRAY_RESTART_THROTTLE_S=90.0`, `XRAY_RESTART_TIMEOUT_S=30.0`, `SYSTEMCTL_ARGS=[...]`.
  - `VlessProxyManager.__init__`: initialize `self._last_xray_restart_monotonic: float = 0.0`.
  - New private `_extract_running_hosts() -> set[str]` — reads `active.json`, returns outbound host set. Safe on missing/malformed file.
  - New private `_reload_xray_systemd(added: set, removed: set) -> tuple[str, int | None]` — throttle check, systemctl call, error handling. Returns (outcome, duration_ms).
  - `refresh_proxy_list`: after writing new config, diff running vs new, call `_reload_xray_systemd` when sets differ, extend the existing `pool_refresh_complete` event with the new keys.
- `tests/test_xray_reload.py` (NEW, 6 tests):
  - `test_set_diff_detects_added_host`
  - `test_set_diff_detects_removed_host`
  - `test_set_diff_no_change_skips_restart`
  - `test_throttle_blocks_second_call_within_90s`
  - `test_systemctl_failure_emits_failed_event`
  - `test_windows_skips_systemctl_silently`
- `scripts/verify_v1.21.sh` (APPEND Phase 68 block): 68-A/B/C/D per SPEC Lock.
- `.planning/phases/68-xray-auto-reload-on-admission-change/68-VERIFICATION.md` (NEW, NEEDS_OPERATOR for sudoers deploy + live restart proof).

---

## Verification

- Local: 6 new tests green, full suite green (+6 from 67 = 336 passed + 3 baseline).
- NEEDS_OPERATOR (68-VERIFICATION.md):
  - EC2 deploy: place sudoers file, validate with `visudo -c`.
  - Force admission change: manually edit `data/vless_pool.json` to drop a host, trigger refresh via `python -c "from proxy_manager import ProxyManager; ProxyManager().refresh_proxy_list()"`, confirm xray PID changes.
  - Watch `data/proxy_events.jsonl` for `pool_refresh_complete` with `xray_restart_triggered: true, restart_outcome: "ok"`.
  - v1.20/v1.19 regression green.

---

## Phase Boundary

**Ships:** admission-diff detection + throttled systemctl reload-or-restart + extended pool_refresh_complete event + 6 unit tests + 4 smoke checks.

**Does NOT ship:**
- Drift visibility in /api/health/deep (Phase 69 — OBS-06/07)
- In-process xray lifecycle (out-of-scope per v1.15 D7)
- Telegram alerting on restart failures (v2)

**Acceptance gate:** 6/6 unit tests green + sudoers entry deployed on EC2 + live restart-triggered event visible in proxy_events.jsonl.

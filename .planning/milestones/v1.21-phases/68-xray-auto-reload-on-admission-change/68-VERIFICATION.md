# Phase 68 Verification — xray Auto-Reload on Admission Change

## Status: CODE SHIPPED locally; awaiting EC2 sudoers deploy + live restart-triggered proof

**Ships locally:**
- [x] 68-01 `_extract_running_hosts` + `_reload_xray_systemd` helpers + locked constants (commit `139b55e`)
- [x] 68-02 `refresh_proxy_list` wiring + `pool_refresh_complete` event schema + `xray_restart_failed` event (commit `4091782`)
- [x] 68-03 `scripts/verify_v1.21.sh` Phase 68 block (68-A/B/C/D/E) + this file (this commit)
- [x] 12/12 tests pass in `tests/test_xray_reload.py`
- [x] Full local suite 342 passed + 3 pre-existing Windows-only baseline failures unchanged
- [x] `bash -n scripts/verify_v1.21.sh` exit 0

**NEEDS_OPERATOR:**

### NEEDS_OPERATOR-1: Deploy sudoers entry on EC2

The systemctl reload-or-restart invocation requires passwordless sudo ONLY on `saleapp-xray.service`. Nothing broader (no `ALL=(ALL) NOPASSWD:ALL`).

```bash
ssh ubuntu@13.60.174.46

# Write the entry to a scratch file, validate, then install.
cat <<'EOF' | sudo tee /etc/sudoers.d/saleapp-xray-reload >/dev/null
ubuntu ALL=(root) NOPASSWD: /bin/systemctl reload-or-restart saleapp-xray, /bin/systemctl restart saleapp-xray
EOF
sudo chmod 0440 /etc/sudoers.d/saleapp-xray-reload
sudo visudo -c -f /etc/sudoers.d/saleapp-xray-reload
# Expect: "/etc/sudoers.d/saleapp-xray-reload: parsed OK"

# Dry-run: confirm the exact invocation is passwordless without actually restarting.
sudo -n /bin/systemctl --help reload-or-restart >/dev/null
# Exit 0 means no password was requested. (The full restart is exercised below.)
```

### NEEDS_OPERATOR-2: EC2 deploy + scheduler restart

```bash
# Backend auto-deploys via github-webhook. Scheduler must restart manually
# to pick up the updated vless/manager.py.
ssh ubuntu@13.60.174.46
cd /home/ubuntu/saleapp
git log -1 --oneline                     # expect HEAD == phase 68-03 commit
sudo systemctl restart saleapp-scheduler
sleep 10
systemctl is-active saleapp-scheduler    # expect: active
```

### NEEDS_OPERATOR-3: Force admission change + verify xray restart

```bash
# Capture baseline xray PID.
OLD_PID=$(pgrep -f 'bin/xray.*active.json' | head -1)
echo "Old xray PID: $OLD_PID"

# Add a dummy host to data/vless_pool.json so the NEXT refresh admits
# a set different from what xray is running. (Direct JSON edit is the
# fastest forcing function — a natural refresh would also work but takes
# up to 1 hour.)
python3 -c '
import json, pathlib
p = pathlib.Path("data/vless_pool.json")
d = json.loads(p.read_text())
# Append a bogus host that will be filtered on the next real refresh.
d["nodes"].append({"host": "127.0.0.55", "port": 443, "name": "force-diff-68"})
p.write_text(json.dumps(d, indent=2))
print("Forced host injected:", d["nodes"][-1]["host"])
'

# Trigger a real refresh in-process (scheduler does this every ~1h naturally).
python3 -c '
import time
from scheduler_service import proxy_manager
before = proxy_manager.pool_count()
proxy_manager.refresh_proxy_list()
after = proxy_manager.pool_count()
print(f"Pool {before} -> {after}")
'

# Verify xray PID changed (systemd reload-or-restart either reloaded in
# place or restarted; the PID changes on full restart, stays on reload).
NEW_PID=$(pgrep -f 'bin/xray.*active.json' | head -1)
echo "New xray PID: $NEW_PID"
[ "$OLD_PID" = "$NEW_PID" ] && echo "Note: same PID — xray supports SIGHUP reload" || \
    echo "PID changed — xray was restarted"

# Tail the most recent pool_refresh_complete event.
tail -n 50 data/proxy_events.jsonl | grep '"event": "pool_refresh_complete"' | tail -1 | python3 -m json.tool
# Expect: restart_outcome == "ok" (first refresh after deploy) or
#         restart_outcome == "unchanged" (if admission yielded same set)
# Expect: added_hosts / removed_hosts non-empty and matching the diff
# Expect: xray_restart_triggered: true AND restart_duration_ms > 0
```

### NEEDS_OPERATOR-4: Throttle verification

```bash
# Fire two admission changes back-to-back; the second MUST be throttled.
ssh ubuntu@13.60.174.46
cd /home/ubuntu/saleapp

python3 -c '
import time
from scheduler_service import proxy_manager
# First refresh — may or may not diff, depending on upstream.
proxy_manager.refresh_proxy_list()
t0 = time.monotonic()
# Force a diff, refresh again within the throttle window.
import json, pathlib
p = pathlib.Path("data/vless_pool.json")
d = json.loads(p.read_text())
d["nodes"].append({"host": "127.0.0.66", "port": 443, "name": "force-diff-68b"})
p.write_text(json.dumps(d, indent=2))
proxy_manager.refresh_proxy_list()
print(f"second refresh at t+{time.monotonic() - t0:.1f}s")
'

# Most recent two pool_refresh_complete events — the second should be
# restart_outcome == "throttled" if within 90s of the first.
tail -n 50 data/proxy_events.jsonl | grep '"event": "pool_refresh_complete"' | tail -2 | python3 -m json.tool
```

### NEEDS_OPERATOR-5: Rollback rehearsal

```bash
# On a throwaway worktree:
git revert 4091782 139b55e     # 68-02 first (depends on 68-01), then 68-01
python3 -m pytest backend/ tests/ -q
# Expect: 330 passed + 3 baseline Windows-only failures (back to pre-68 baseline)
bash -n scripts/verify_v1.21.sh   # expect exit 0 (script still parses after revert)
sudo systemctl restart saleapp-scheduler
sleep 10
systemctl is-active saleapp-scheduler   # expect: active
# Confirm no stale sudoers entry — sudoers file is orthogonal to the git
# change and can be left in place safely; removing it is optional:
# sudo rm /etc/sudoers.d/saleapp-xray-reload
```

### NEEDS_OPERATOR-6: Cross-version regression

```bash
bash scripts/verify_v1.21.sh 67      # expect: 67-A/B/C/D green
bash scripts/verify_v1.21.sh 68      # expect: 68-A/B/C/D/E green
bash scripts/verify_v1.21.sh all     # expect: all green + v1.20 19/19 + v1.19 24/24
```

## Success Criteria

| Criterion | Status | Evidence |
|---|---|---|
| 1. VlessProxyManager exports `_extract_running_hosts` + `_reload_xray_systemd` | code_complete | commit `139b55e`, 68-A / 68-B smoke |
| 2. `XRAY_RESTART_THROTTLE_S` = 90.0, `XRAY_RESTART_TIMEOUT_S` = 30.0, argv locked | code_complete | `test_reload_constants_locked` green |
| 3. `refresh_proxy_list` diffs running vs admitted and invokes reload only on diff | code_complete | `test_refresh_skips_reload_when_admitted_set_unchanged`, `test_refresh_triggers_reload_when_admitted_set_differs` |
| 4. Throttle blocks second call within 90s without invoking subprocess | code_complete | `test_reload_throttled_within_window` |
| 5. `pool_refresh_complete` event carries full admission-diff + restart outcome | code_complete | commit `4091782` (OBS-07 partial) |
| 6. `xray_restart_failed` emitted as dedicated event on restart failure | code_complete | `test_refresh_emits_xray_restart_failed_event_on_systemctl_failure` |
| 7. Windows skip + legacy in-process-xray skip | code_complete | `test_reload_skipped_on_windows`, `test_reload_skipped_when_in_process_xray_owned` |
| 8. Sudoers entry deployed on EC2 | needs_operator | NEEDS_OPERATOR-1 |
| 9. Live: forced admission change causes xray reload + `xray_restart_triggered: true` | needs_operator | NEEDS_OPERATOR-3 |
| 10. Throttle verified live (second refresh within 90s → `restart_outcome: "throttled"`) | needs_operator | NEEDS_OPERATOR-4 |
| 11. Rollback rehearsal green | needs_operator | NEEDS_OPERATOR-5 |
| 12. Cross-version regression (v1.20 + v1.19) green | needs_operator | NEEDS_OPERATOR-6 |

## Phase Boundary

**Ships:** admission-diff detection + throttled `systemctl reload-or-restart saleapp-xray` + extended `pool_refresh_complete` event + 12 unit tests + 5 smoke checks.

**Does NOT ship:**
- `/api/health/deep` drift block (Phase 69 — OBS-06)
- Full `pool_refresh_complete` schema surfaced to `/admin/status.reliability` (Phase 69 — OBS-07 completion)
- In-process xray lifecycle (out of scope per v1.15 D7)
- Telegram alerting on `xray_restart_failed` (v2)

**Acceptance gate:** 12/12 unit tests green + 5/5 smoke checks on EC2 + sudoers entry deployed + live restart-triggered event visible in `data/proxy_events.jsonl`.

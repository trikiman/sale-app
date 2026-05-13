# Phase 69 Verification — Drift Visibility

## Status: CODE SHIPPED locally; awaiting EC2 deploy + live drift-injection proof

**Ships locally:**
- [x] 69-01 `_compute_xray_drift_block` helper + OBS-06 thresholds + first-seen tracking (commit `0888b58`)
- [x] 69-02 `_build_reliability_snapshot` wiring + `pool_refresh_complete.success_rate_drops` (commit `0a544a3`)
- [x] 69-03 `scripts/verify_v1.21.sh` Phase 69 block + this file (this commit)
- [x] 12/12 tests pass in `tests/test_xray_drift_health.py`
- [x] 13/13 tests pass in `tests/test_xray_reload.py` (existing 12 + new success_rate_drops test)
- [x] Full local suite 355 passed + 3 baseline Windows-only failures unchanged
- [x] `bash -n scripts/verify_v1.21.sh` exit 0

**NEEDS_OPERATOR:**

### NEEDS_OPERATOR-1: EC2 deploy

Backend auto-deploys via github-webhook on push. Scheduler must restart manually to pick up `vless/manager.py` changes (pool_refresh_complete success_rate_drops).

```bash
ssh ubuntu@13.60.174.46
cd /home/ubuntu/saleapp
git log -1 --oneline                     # expect HEAD == 69-03 commit
sudo systemctl restart saleapp-scheduler
sleep 10
systemctl is-active saleapp-scheduler    # expect: active
systemctl is-active saleapp-backend      # expect: active
```

### NEEDS_OPERATOR-2: External-curl baseline (healthy state)

```bash
# From local workstation:
curl -sS https://vkusvillsale.vercel.app/api/health/deep | python3 -m json.tool | grep -A 6 xray_drift
# Expect:
#   "xray_drift": {
#       "admitted_hosts": <N>,
#       "active_outbounds": <N>,
#       "drift_count": 0,
#       "drifted_hosts": [],
#       "first_seen_at": null
#   }

curl -sS -o /dev/null -w "HTTP %{http_code}\n" https://vkusvillsale.vercel.app/api/health/deep
# Expect: HTTP 200
```

### NEEDS_OPERATOR-3: Inject drift + verify block flips

```bash
ssh ubuntu@13.60.174.46
cd /home/ubuntu/saleapp

# Capture baseline xray host count.
BEFORE=$(python3 -c '
import json, pathlib
pool = json.loads(pathlib.Path("data/vless_pool.json").read_text())
cfg = json.loads(pathlib.Path("bin/xray/configs/active.json").read_text())
pool_hosts = {n["host"] for n in pool.get("nodes", []) if n.get("host")}
cfg_hosts = set()
for o in cfg.get("outbounds", []):
    for v in (o.get("settings") or {}).get("vnext") or []:
        if v.get("address"):
            cfg_hosts.add(v["address"])
print(f"pool={len(pool_hosts)} cfg={len(cfg_hosts)} drift={len(pool_hosts ^ cfg_hosts)}")
')
echo "BEFORE: $BEFORE"

# Inject drift: hand-edit data/vless_pool.json to add one bogus host
# (backend reads pool JSON, active.json unchanged → drift = 1).
python3 -c '
import json, pathlib
p = pathlib.Path("data/vless_pool.json")
d = json.loads(p.read_text())
d["nodes"].append({"host": "127.0.0.99", "port": 443, "name": "drift-inject-69"})
p.write_text(json.dumps(d, indent=2))
print("Injected 127.0.0.99 into pool")
'

# Wait < 5 min — drift exists but grace window not yet expired.
# /api/health/deep should show drift_count=1, drifted_hosts=["127.0.0.99"],
# but reasons[] should NOT yet include xray_stale_config.
sleep 10
curl -sS https://vkusvillsale.vercel.app/api/health/deep | python3 -m json.tool | grep -E 'xray_drift|reasons|status'
# Expect: drift_count=1, status=healthy, NO xray_stale_config in reasons

# Wait 5+ min for the degraded threshold to trip.
sleep 300
curl -sS -o /dev/null -w "HTTP %{http_code}\n" https://vkusvillsale.vercel.app/api/health/deep
# Expect: HTTP 503
curl -sS https://vkusvillsale.vercel.app/api/health/deep | python3 -m json.tool | grep -E 'xray_stale_config|status'
# Expect: status="degraded", reasons contains "xray_stale_config:1_nodes_drifted"
```

### NEEDS_OPERATOR-4: Resolve drift + verify recovery

```bash
ssh ubuntu@13.60.174.46
cd /home/ubuntu/saleapp

# Remove the injected host.
python3 -c '
import json, pathlib
p = pathlib.Path("data/vless_pool.json")
d = json.loads(p.read_text())
d["nodes"] = [n for n in d["nodes"] if n.get("host") != "127.0.0.99"]
p.write_text(json.dumps(d, indent=2))
print("Removed 127.0.0.99 from pool")
'

# Wait for /api/health/deep cache (each hit is live so ~5-10s).
sleep 10
curl -sS https://vkusvillsale.vercel.app/api/health/deep | python3 -m json.tool | grep -E 'xray_drift|status'
# Expect: drift_count=0, status=healthy
curl -sS -o /dev/null -w "HTTP %{http_code}\n" https://vkusvillsale.vercel.app/api/health/deep
# Expect: HTTP 200
```

### NEEDS_OPERATOR-5: pool_refresh_complete.success_rate_drops verification

```bash
ssh ubuntu@13.60.174.46
cd /home/ubuntu/saleapp

# Force a refresh so a fresh pool_refresh_complete lands.
python3 -c '
from scheduler_service import proxy_manager
proxy_manager.refresh_proxy_list()
'

# Tail the most recent pool_refresh_complete event.
tail -n 100 data/proxy_events.jsonl | grep '"event": "pool_refresh_complete"' | tail -1 | python3 -m json.tool
# Expect ALL Phase-68 + Phase-69 keys:
#   admitted_count, admitted_hosts_before, admitted_hosts_after,
#   added_hosts, removed_hosts, xray_restart_triggered,
#   restart_duration_ms, restart_outcome, restart_stderr_tail,
#   success_rate_drops
```

### NEEDS_OPERATOR-6: Rollback rehearsal

```bash
# On a throwaway worktree:
git revert 0a544a3 0888b58      # 69-02 first (depends on 69-01), then 69-01
python3 -m pytest backend/ tests/ -q
# Expect: 342 passed + 3 baseline (back to post-Phase-68 baseline)
bash -n scripts/verify_v1.21.sh  # expect exit 0
sudo systemctl restart saleapp-backend
sudo systemctl restart saleapp-scheduler
curl -sS https://vkusvillsale.vercel.app/api/health/deep | python3 -m json.tool | grep -c xray_drift
# Expect: 0 (block gone after revert)
```

### NEEDS_OPERATOR-7: Full v1.21 smoke

```bash
bash scripts/verify_v1.21.sh 67     # expect: 67-A/B/C/D green
bash scripts/verify_v1.21.sh 68     # expect: 68-A/B/C/D/E green
bash scripts/verify_v1.21.sh 69     # expect: 69-A/B/C/D green
bash scripts/verify_v1.21.sh all    # expect: all 13 v1.21 checks + v1.20 19/19 + v1.19 24/24
```

## Success Criteria

| Criterion | Status | Evidence |
|---|---|---|
| 1. `/api/health/deep` gains `xray_drift` block when pool + config available | code_complete | commit `0a544a3`, `test_reliability_snapshot_attaches_drift_block_when_present` |
| 2. `xray_drift` block absent when pool unavailable (no-ledger fallback) | code_complete | `test_xray_drift_block_absent_when_pool_unavailable` |
| 3. `drift_count = \|admitted △ active_outbounds\|` correct | code_complete | `test_xray_drift_block_reports_symmetric_difference` |
| 4. Drift > 5 min → reasons gets `xray_stale_config:{N}_nodes_drifted`, status=degraded | code_complete | `test_reliability_snapshot_degraded_when_drift_persisted` |
| 5. Drift + cycle_age > 10 min → status=unhealthy | code_complete | `test_reliability_snapshot_unhealthy_when_drift_plus_stale_cycle` |
| 6. First-seen timestamp resets when drifted-set changes | code_complete | `test_xray_drift_first_seen_resets_on_set_change` |
| 7. `pool_refresh_complete` carries `success_rate_drops[]` | code_complete | `test_pool_refresh_complete_includes_success_rate_drops` |
| 8. `/admin/status.reliability.xray_drift` mirrors the block | code_complete | `/admin/status` already returns `_build_reliability_snapshot()` output — no extra wiring needed |
| 9. Live: external curl returns block when healthy | needs_operator | NEEDS_OPERATOR-2 |
| 10. Live: injected drift flips endpoint to 503 after 5 min | needs_operator | NEEDS_OPERATOR-3 |
| 11. Live: drift removal returns endpoint to 200 within 30s | needs_operator | NEEDS_OPERATOR-4 |
| 12. Live: `success_rate_drops` present in fresh pool_refresh_complete | needs_operator | NEEDS_OPERATOR-5 |
| 13. v1.20 + v1.19 regression green | needs_operator | NEEDS_OPERATOR-7 |

## Phase Boundary

**Ships:** `/api/health/deep` + `/admin/status.reliability` `xray_drift` block, OBS-06 degraded (5 min) / unhealthy (+ stale cycle) thresholds, `pool_refresh_complete.success_rate_drops` completing OBS-07, 12 drift unit tests + 1 reload schema test, 4 smoke checks.

**Does NOT ship:**
- `admin.html` UI card surfacing drift (deferred to v1.22 UX debt milestone)
- Telegram alerts on drift (v2 REL-FUT-05)
- Historical drift trace / rate-of-change panels (future observability milestone)

**Acceptance gate:** 12/12 drift unit tests green + 4/4 smoke on EC2 + external curl proves drift injection flips endpoint to 503 and recovery returns it to 200.

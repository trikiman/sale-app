# Phase 67 Verification — Admitted-Node Self-Healing Loop

## Status: CODE SHIPPED locally; awaiting EC2 deploy + live verification

**Ships locally:**
- [x] 67-01 `VlessProxyManager` success_rate + dead-node exclusion (commit `aa433ff`)
- [x] 67-02 `keepalive/reprobe.py` daemon + scheduler wiring + call-site outcome recording (commit `0598224`)
- [x] 67-03 `scripts/verify_v1.21.sh` + this verification skeleton (this commit)
- [x] 6/6 tests pass in `tests/test_reprobe_loop.py`
- [x] Full local suite 330 passed + 3 pre-existing Windows-only baseline failures unchanged
- [x] `bash -n scripts/verify_v1.21.sh` exit 0

**NEEDS_OPERATOR:**

### NEEDS_OPERATOR-1: EC2 deploy + scheduler restart

```bash
# Auto-deploy handles git pull (github-webhook on backend). Scheduler must restart manually:
ssh ubuntu@13.60.174.46
cd /home/ubuntu/saleapp
git log -1 --oneline    # verify HEAD has phase 67-03 commit
sudo systemctl restart saleapp-scheduler
sleep 130  # past REPROBE_BOOT_GRACE_S (120s) + first cycle settle
```

### NEEDS_OPERATOR-2: Verify re-probe daemon alive

```bash
cd /home/ubuntu/saleapp
grep 'reprobe_cycle_complete' data/proxy_events.jsonl | tail -3
# Expect: at least 1 line with
# {"event":"reprobe_cycle_complete","admitted_count":N,"probed":N,"passed":M,"failed_hosts":[],"duration_ms":...}
bash scripts/verify_v1.21.sh 67
# Expect: 4/4 green (67-A/B/C/D)
```

### NEEDS_OPERATOR-3: Induced-failure end-to-end (REL-13 live demo)

```bash
# Block vkusvill.ru via hosts override for 12 min so ≥ 1 re-probe cycle hits it:
echo "0.0.0.0 vkusvill.ru" | sudo tee -a /etc/hosts
sleep 720  # past next re-probe cycle (10 min) + settle
tail -n 5 data/proxy_events.jsonl | grep reprobe_cycle_complete
# Expect: most recent cycle shows "passed":0, "failed_hosts":[hosts...]
curl -s http://127.0.0.1:8000/api/health/deep | python3 -m json.tool | grep -E 'pool|reasons'
# Expect: reasons[] gains "pool_below_min_healthy:..." (admitted count dropped after cooldown)

# Restore hosts:
sudo sed -i '/0.0.0.0 vkusvill.ru/d' /etc/hosts
sleep 300
# Scheduler's next get_working_proxy triggers ensure_pool → refresh_proxy_list automatically.
# After refresh, admitted count should recover.
bash scripts/verify_v1.21.sh 67
# Expect: 67-A/B/C/D green again; pool healthy.
```

### NEEDS_OPERATOR-4: Rollback rehearsal

```bash
# On a throwaway worktree:
git revert 0598224 aa433ff  # 67-02 first (depends on 67-01), then 67-01
python3 -m pytest backend/ tests/ -q
# Expect: only 3 baseline Windows-only failures
bash -n scripts/verify_v1.20.sh     # exit 0 (earlier milestone's smoke should still parse)
sudo systemctl restart saleapp-scheduler
# Confirm scheduler still runs without the reprobe thread;
# data/proxy_events.jsonl stops emitting reprobe_cycle_complete.
```

### NEEDS_OPERATOR-5: Cross-version regression

```bash
bash scripts/verify_v1.20.sh all
# Expect: 19/19 Phase 62-66.1 smoke checks green
bash scripts/verify_v1.19.sh all
# Expect: 24/24 green
```

## Success Criteria

| Criterion | Status | Evidence |
|---|---|---|
| 1. VlessProxyManager exports record_outcome + success_rate + iter_admitted_hosts | code_complete | commit `aa433ff`, 67-01-PLAN.md diff |
| 2. Dead nodes (rate < 0.1, samples ≥ 20) excluded from pool_snapshot active_outbounds | code_complete | `test_dead_node_excluded_from_active_outbounds` green |
| 3. keepalive.reprobe daemon fires every 10 min | code_complete | commit `0598224`, REPROBE_INTERVAL_S=600.0 |
| 4. Scheduler spawns `scheduler-reprobe` thread | code_complete | scheduler_service.py post-keepalive block |
| 5. Failed re-probe routes to `mark_vkusvill_blocked` with reason="reprobe_fail" | code_complete | `test_reprobe_cycle_marks_failed_host_cooldown` green |
| 6. Boot grace respected | code_complete | `test_reprobe_boot_grace_respected` green |
| 7. scripts/verify_v1.21.sh has Phase 67 block + v1.20 + v1.19 regression | code_complete | 67-03 script |
| 8. Live EC2: reprobe_cycle_complete events in proxy_events.jsonl | needs_operator | NEEDS_OPERATOR-2 |
| 9. Live EC2: induced failure detected, pool recovers post-restore | needs_operator | NEEDS_OPERATOR-3 |
| 10. v1.20 + v1.19 regression green on EC2 | needs_operator | NEEDS_OPERATOR-5 |

## Phase Boundary

**Ships:** 10-min re-probe daemon + success_rate tracking + dead-node exclusion + 6 tests + 4 smoke checks.

**Does NOT ship:**
- xray auto-reload on admission change (Phase 68 — REL-14)
- Drift visibility via /api/health/deep block (Phase 69 — OBS-06/07)
- Telegram alerting on pool health drops (v2 REL-FUT-05)

**Acceptance gate:** 6/6 tests green + 4/4 smoke on EC2 + induced-failure reproduction passes.

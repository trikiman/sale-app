# Phase 62 Verification

**Status:** NEEDS_OPERATOR
**Created:** 2026-05-10
**Commits verified (local):** `51888f7` (62-01), `700358b` (62-02)

This skeleton was produced by the automated executor. Sections flagged
**NEEDS_OPERATOR** require SSH access to the EC2 scraper host and/or live
latency measurement — they must be executed by a human operator per Plan
62-03 (`autonomous: false`).

---

## Local verification (completed by automation)

- Unit tests: `python -m pytest tests/test_keepalive_warmup.py -v`
  - 7 passed (test_jsonl_schema, test_anti_spam_ceiling, test_pool_unhealthy_gate, test_breaker_open_gate, test_cart_add_active_cancellation, test_stop_event_clean_shutdown, test_jsonl_rotation_at_ten_mb)
- Full test suite: `python -m pytest tests/ -q`
  - 214 passed, 2 skipped, 3 pre-existing Windows-specific failures in `tests/test_vless_xray.py` / `tests/test_vless_config_gen.py` (unrelated to Phase 62; same baseline as before 62-01)
- Import smoke:
  - `python -c "from keepalive.warmup import start_warmup_loop, CART_ADD_ACTIVE, NUDGE_QUEUE, hash_user_id"` → ok
  - `python -c "import scheduler_service"` → ok
  - `python -c "from backend.main import app"` → ok
  - `python -c "from cart.vkusvill_api import VkusVillCart"` → ok
- Smoke script syntax: `bash -n scripts/verify_v1.20.sh` → ok (exit 0)
- Commit graph:
  - `51888f7` feat(62-01): keepalive/warmup.py daemon + scheduler integration
  - `700358b` feat(62-02): nudge triggers + cart-add race flag + tests + v1.20 smoke

---

## Operator-only sections (NEEDS_OPERATOR)

- [ ] Pre-deploy baseline cart-add p50/p95/p99 (Plan 62-03 Step 2, n=50)
- [ ] Deploy `phase-62-ship` branch to EC2 (Plan 62-03 Step 3)
- [ ] Observe warmup cycle at t+1 / 5 / 12 / 22 min (Plan 62-03 Step 4)
- [ ] `scripts/verify_v1.20.sh 62` on EC2 — 62-A..62-E all green (Plan 62-03 Step 5)
- [ ] `scripts/verify_v1.19.sh all` regression gate — 24/24 green (Plan 62-03 Step 6)
- [ ] Post-deploy cart-add p50/p95/p99 + delta vs baseline (Plan 62-03 Step 7, n=50)
- [ ] Warmup per-attempt latency histogram from JSONL — p95 <= 3 s (Plan 62-03 Step 8)
- [ ] Rollback rehearsal on throwaway worktree (Plan 62-03 Step 9, mandatory pre-merge)
- [ ] Go/no-go stamp with all 6 checkboxes signed off

### Pre-deploy baseline (fill in after Plan 62-03 Step 2)

| Metric | Value (ms) |
|---|---|
| p50 | _TBD_ |
| p95 | _TBD_ |
| p99 | _TBD_ |
| Samples | _TBD / 50_ |

### Post-deploy latency (fill in after Plan 62-03 Step 7)

|         | p50 | p95 | p99 |
|---------|-----|-----|-----|
| baseline | _TBD_ | _TBD_ | _TBD_ |
| post-62 | _TBD_ | _TBD_ | _TBD_ |
| delta   | _TBD_ | _TBD_ | _TBD_ |

**VERDICT:** _TBD — PASS requires p95 <= 6000 ms AND (p95 - baseline) <= 500 ms_

### Warmup per-attempt latency (fill in after Plan 62-03 Step 8)

| Metric | Value (ms) |
|---|---|
| p50 | _TBD_ |
| p95 | _TBD_ |
| p99 | _TBD_ |
| n (ok attempts) | _TBD_ |

**PERF-05 p95 budget (<= 3000 ms):** _TBD_

### Rollback rehearsal (fill in after Plan 62-03 Step 9)

- Throwaway worktree: `git worktree add /tmp/saleapp-rollback-rehearsal phase-62-ship`
- Revert range: `git revert --no-edit 700358b 51888f7`
- Post-revert diff vs `v1.19-ship`: _TBD — expected empty for scheduler_service.py, backend/main.py, cart/vkusvill_api.py_
- `keepalive/` directory present after revert: _TBD — expected NO_
- `python -m pytest tests/ -q`: _TBD — expected green (same baseline)_
- Worktree cleanup: `git worktree remove /tmp/saleapp-rollback-rehearsal --force`

### Live rollback procedure (reference for operator if needed)

```bash
ssh "$EC2_HOST" bash <<'EOSSH'
set -euo pipefail
cd /home/ubuntu/saleapp
git revert --no-edit 700358b 51888f7
sudo systemctl restart saleapp-scheduler
sudo systemctl restart saleapp-backend
EOSSH

# From operator local:
bash scripts/verify_v1.19.sh all   # must be 24/24 green
```

### Go/No-Go stamp

- [ ] All 5 Phase-62 smoke checks green (62-A..62-E)
- [ ] v1.19 regression 24/24 green
- [ ] Cart-add p95 <= 6 s on warm path
- [ ] Cart-add p95 regression <= 500 ms vs baseline
- [ ] Warmup p95 <= 3 s
- [ ] Rollback rehearsed and passes

**Operator sign-off:** _name, YYYY-MM-DD_

---

## Deferred until operator completes above

- Merge of `phase-62-ship` branch to `main`
- Final phase status update in `.planning/STATE.md`
- Tag/release bookkeeping for v1.20 milestone

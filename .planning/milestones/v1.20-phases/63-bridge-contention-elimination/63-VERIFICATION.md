# Phase 63 Verification — Bridge Contention Elimination

**Milestone:** v1.20
**Phase:** 63 (bridge-contention-elimination)
**Requirements covered:** PERF-06, PERF-07, OPS-09, OPS-10, OPS-11

Status key:
- `PASS` — operator verified, evidence below
- `NEEDS_OPERATOR` — runtime/deploy step, fill before merge
- `FAIL` — blocker

---

## 1. Local Implementation Gate (filled during 63-01/63-02 execution)

| Check | Status | Evidence |
|---|---|---|
| `cart/bridge_semaphore.py` imports cleanly | PASS | `python -c "from cart.bridge_semaphore import CART_ADD_IN_FLIGHT, cart_add_slot, scraper_slot, is_pending_cache_fresh" -> exit 0` |
| Locked constants present | PASS | `CART_ITEMS_CACHE_TTL_S == 12.0`, `SCRAPER_BRIDGE_TIMEOUT_S == 10.0` asserted in 63-A smoke |
| `cart/vkusvill_api.py` still imports cleanly | PASS | `python -c "from cart.vkusvill_api import VkusVillCart" -> exit 0` |
| `backend/main.py` still imports cleanly | PASS | `python -c "from backend.main import app" -> exit 0` |
| 7/7 bridge_semaphore unit tests green (local, Windows) | PASS | `python -m pytest tests/test_bridge_semaphore.py -q -> 7 passed in 0.65s` |
| Phase 62 test suite unchanged | PASS | CART_ADD_ACTIVE flag wiring in `cart/vkusvill_api.py::add()` is byte-preserved; bridge semaphore lives in a separate try/except beside it |
| All 3 scrapers parse cleanly | PASS | `python -c "import ast; [ast.parse(open(f,encoding='utf-8').read()) for f in ['scrape_green.py','scrape_red.py','scrape_yellow.py']]; print('ok')" -> ok` |
| `scripts/verify_v1.20.sh` bash syntax clean | PASS | `bash -n scripts/verify_v1.20.sh -> exit 0` |

---

## 2. EC2 Deploy (63-03) — NEEDS_OPERATOR

### 2.1 Deploy Log

```
NEEDS_OPERATOR: paste output of
  ssh "$EC2_HOST" "cd /home/ubuntu/saleapp && git fetch origin && git checkout <v1.20-branch> && git pull --ff-only"
  ssh "$EC2_HOST" "sudo systemctl restart saleapp-backend saleapp-scheduler"
  ssh "$EC2_HOST" "sudo systemctl status saleapp-backend --no-pager | head -20"
  ssh "$EC2_HOST" "sudo systemctl status saleapp-scheduler --no-pager | head -20"
```

Deploy timestamp: `NEEDS_OPERATOR` (UTC)
Commit deployed: `NEEDS_OPERATOR` (SHA)

### 2.2 Smoke Verify

| Check | Status | Evidence |
|---|---|---|
| `scripts/verify_v1.20.sh 63` | NEEDS_OPERATOR | Expect 4/4 PASS |
| `scripts/verify_v1.20.sh 62` | NEEDS_OPERATOR | Expect 5/5 PASS (no Phase-62 regression) |
| `scripts/verify_v1.19.sh all` | NEEDS_OPERATOR | Expect 24/24 PASS (v1.19 regression gate) |

Paste full output for each:

```
NEEDS_OPERATOR: ./scripts/verify_v1.20.sh 63
```

```
NEEDS_OPERATOR: ./scripts/verify_v1.20.sh 62
```

```
NEEDS_OPERATOR: ./scripts/verify_v1.19.sh all
```

---

## 3. OPS-10 Live Latency Gate — NEEDS_OPERATOR

### 3.1 Baseline (Phase 62 only, captured previously)

```
NEEDS_OPERATOR: paste Phase-62 p95 from .planning/phases/62-sessid-keepalive-warmup/62-VERIFICATION.md
```

### 3.2 Phase 63 Measurement (during active scraper window)

Procedure: `63-03-PLAN.md § Step 3`.

Samples: 50
Scraper running: `NEEDS_OPERATOR` (e.g. "scrape_green.py active")
Test user: `NEEDS_OPERATOR` (hash)
Test product: `NEEDS_OPERATOR` (id)

Result:

| Metric | Value (ms) | Gate |
|---|---|---|
| p50 | `NEEDS_OPERATOR` | - |
| p95 | `NEEDS_OPERATOR` | <= 4500 ms AND <= baseline + 500 ms |
| max | `NEEDS_OPERATOR` | - |

Gate outcome: `NEEDS_OPERATOR` (PASS / FAIL)

---

## 4. Proxy Events Sample — NEEDS_OPERATOR

```
NEEDS_OPERATOR: paste `ssh "$EC2_HOST" "tail -50 /home/ubuntu/saleapp/data/proxy_events.jsonl | grep -E 'cart_items_cache_|scraper_paused_for_cart_add'"`

Expected at least:
- 1+ line with event == "cart_items_cache_hit"
- 1+ line with event == "scraper_paused_for_cart_add"
```

---

## 5. OPS-11 Rollback Rehearsal — NEEDS_OPERATOR

Procedure: `63-03-PLAN.md § Step 4`.

### 5.1 Revert Output

```
NEEDS_OPERATOR: paste
  ssh "$EC2_HOST" "cd /tmp/saleapp-rollback && git revert --no-edit <63-01-sha> <63-02-sha>"
```

### 5.2 Post-Revert Import Check

Both MUST exit 0 without `ImportError`:

```
NEEDS_OPERATOR: ssh "$EC2_HOST" "cd /tmp/saleapp-rollback && python3 -c 'from cart.vkusvill_api import VkusVillCart; print(\"ok\")'"
NEEDS_OPERATOR: ssh "$EC2_HOST" "cd /tmp/saleapp-rollback && python3 -c 'from backend.main import app; print(\"ok\")'"
```

### 5.3 Post-Revert Smoke

```
NEEDS_OPERATOR: run `scripts/verify_v1.20.sh 62` against the reverted worktree's checked-out commit (or against the main branch after a temporary revert on a throwaway branch). Expect 5/5.
```

Rollback rehearsal outcome: `NEEDS_OPERATOR` (PASS / FAIL)

---

## 6. Merge Decision

| Gate | Status |
|---|---|
| Local implementation | PASS |
| EC2 deploy + smoke | NEEDS_OPERATOR |
| Live p95 gate | NEEDS_OPERATOR |
| Rollback rehearsed | NEEDS_OPERATOR |
| v1.19 regression | NEEDS_OPERATOR |
| proxy_events sample | NEEDS_OPERATOR |

Merge allowed when all rows above are PASS.

Operator sign-off: `NEEDS_OPERATOR` (name + UTC timestamp)

---

*Verification: 63-VERIFICATION.md*
*Created (skeleton): 2026-05-10 — fill during 63-03 execution*

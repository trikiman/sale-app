# Phase 64 Verification - VkusVill API Surface Spike

**Milestone:** v1.20
**Phase:** 64 (vkusvill-api-surface-spike)
**Requirements covered:** PERF-08, PERF-09, OPS-09, OPS-10, OPS-11

Status key:
- `PASS` - operator verified, evidence below
- `NEEDS_OPERATOR` - runtime / deploy step, fill before merge
- `FAIL` - blocker

---

## 1. Local Implementation Gate (filled during 64-01 / 64-02 execution)

| Check | Status | Evidence |
|---|---|---|
| `cart/vkusvill_api.py` exports `USE_FAST_CART_ADD_ENDPOINT` + `FAST_CART_ADD_URL` | PASS | `python -c "from cart.vkusvill_api import USE_FAST_CART_ADD_ENDPOINT, FAST_CART_ADD_URL; assert USE_FAST_CART_ADD_ENDPOINT is False; assert FAST_CART_ADD_URL is None; print('ok')"` prints `ok` |
| Default flag=False, URL=None preserved | PASS | same as above |
| `cart/vkusvill_api.py` still imports cleanly | PASS | `python -c "from cart.vkusvill_api import VkusVillCart; print('ok')"` prints `ok` |
| `backend/main.py` still imports cleanly | PASS | `python -c "from backend.main import app; print('ok')"` prints `ok` (no new import side-effects) |
| 3/3 feature-flag unit tests green (local, Windows) | PASS | `python -m pytest tests/test_cart_feature_flag.py -v` prints `3 passed in 0.11s` |
| Full suite still at baseline plus 3 new tests | PASS | `python -m pytest tests/ -q` prints `224 passed, 2 skipped, 3 known-fail` (pre-existing failures in `test_vless_config_gen.py` and `test_vless_xray.py` unchanged) |
| Ablation harness `--dry-run` works | PASS | `python scripts/ablate_basket_add_payload.py --dry-run --user-id 12345 --product-id 731 --n-per-field 2` exits 0 with valid JSON |
| `scripts/verify_v1.20.sh` bash syntax clean | PASS | `bash -n scripts/verify_v1.20.sh` exits 0 |
| Research skeleton present with NEEDS_OPERATOR sections | PASS | `.planning/research/v1.20-API-SPIKE.md` has 6 sections (A-F); A-E are NEEDS_OPERATOR |

---

## 2. Live HAR Capture - NEEDS_OPERATOR

```
NEEDS_OPERATOR: HAR captured at <path>. Captured from Chrome <version>
through xray socks5://127.0.0.1:10808, authenticated as test account
<user-id>. Endpoints observed during add-to-cart:
  - basket_add.php (baseline)
  - <candidate endpoint 1, if any>
  - <candidate endpoint 2, if any>
```

Fill `.planning/research/v1.20-API-SPIKE.md` Section A note + Section B endpoint table.

---

## 3. Live Ablation Sweep - NEEDS_OPERATOR

For each reachable endpoint, one entry below.

### 3.1 baseline /ajax/delivery_order/basket_add.php

```
NEEDS_OPERATOR: paste output path + verdict
  python scripts/ablate_basket_add_payload.py \
    --user-id <test-user-id> \
    --product-id <test-product-id> \
    --n-per-field 20 \
    --output .planning/research/ablation-basket_add_php.json
```

Result:
- baseline success_rate: `NEEDS_OPERATOR`
- baseline p50 / p95 (ms): `NEEDS_OPERATOR`
- `verdict.droppable`: `NEEDS_OPERATOR`
- `verdict.required`: `NEEDS_OPERATOR`

### 3.2 candidate endpoints (if any)

Repeat section 3.1 per candidate. Fill `.planning/research/v1.20-API-SPIKE.md` Section C.

---

## 4. Go/No-Go Decision - NEEDS_OPERATOR

Apply the 4-case decision tree in Section D of the research doc.

Operator decision: `NEEDS_OPERATOR` (GO / NO-GO / REJECT)
Rationale (2-3 sentences): `NEEDS_OPERATOR`
Signed: `NEEDS_OPERATOR` (name + UTC timestamp)

---

## 5. If GO - Swap Implementation + EC2 Deploy - NEEDS_OPERATOR

Only fill this section if Section 4 decision is GO.

### 5.1 Code changes

```
NEEDS_OPERATOR: paste git diff summary for
  cart/vkusvill_api.py    (FAST_CART_ADD_URL populated, _add_fast() added, NotImplementedError removed)
  tests/test_cart_feature_flag.py   (new test: fast path is taken when flag on)
```

### 5.2 EC2 deploy log

```
NEEDS_OPERATOR: paste output of
  ssh "$EC2_HOST" "cd /home/ubuntu/saleapp && git fetch origin && git checkout <v1.20-branch> && git pull --ff-only"
  ssh "$EC2_HOST" "sudo systemctl restart saleapp-backend saleapp-scheduler"
  ssh "$EC2_HOST" "sudo systemctl status saleapp-backend --no-pager | head -20"
```

Deploy timestamp: `NEEDS_OPERATOR` (UTC)
Commit deployed: `NEEDS_OPERATOR` (SHA)

### 5.3 Flag flip (only after 5.4 + 5.5 pass)

```
NEEDS_OPERATOR: paste output of systemd drop-in edit + daemon-reload
```

---

## 6. Smoke Verify - NEEDS_OPERATOR

| Check | Status | Evidence |
|---|---|---|
| `scripts/verify_v1.20.sh 64` | NEEDS_OPERATOR | Expect 3/3 PASS pre-swap; 3/3 PASS post-swap with 64-B updated to assert populated URL |
| `scripts/verify_v1.20.sh 63` | NEEDS_OPERATOR | Expect 4/4 PASS (no regression) |
| `scripts/verify_v1.20.sh 62` | NEEDS_OPERATOR | Expect 5/5 PASS (no regression) |
| `scripts/verify_v1.19.sh all` | NEEDS_OPERATOR | Expect 24/24 PASS (milestone regression gate) |

Paste full output:

```
NEEDS_OPERATOR: ./scripts/verify_v1.20.sh 64
```

```
NEEDS_OPERATOR: ./scripts/verify_v1.20.sh all
```

```
NEEDS_OPERATOR: ./scripts/verify_v1.19.sh all
```

---

## 7. OPS-10 Live Latency Gate - NEEDS_OPERATOR

### 7.1 Baseline (Phase 63 final)

```
NEEDS_OPERATOR: paste Phase-63 p95 from 63-VERIFICATION.md
```

### 7.2 Phase 64 Measurement (only if GO landed + flag flipped on)

Samples: 50 synthetic cart-adds over 5-min window
Test user: `NEEDS_OPERATOR`
Test product: `NEEDS_OPERATOR`

| Metric | Value (ms) | Gate |
|---|---|---|
| p50 | `NEEDS_OPERATOR` | - |
| p95 | `NEEDS_OPERATOR` | <= 4000 ms (milestone target) AND no more than 500 ms above Phase-63 baseline |
| max | `NEEDS_OPERATOR` | - |

Gate outcome: `NEEDS_OPERATOR` (PASS / FAIL)

### 7.3 NO-GO path latency gate

If Section 4 is NO-GO: payload trim should not regress p95. Paste before/after from Section E of the research doc.

Pre-trim p95: `NEEDS_OPERATOR`
Post-trim p95: `NEEDS_OPERATOR`
Delta: `NEEDS_OPERATOR` ms (target <= 0)

---

## 8. OPS-11 Rollback Rehearsal - NEEDS_OPERATOR

Procedure: `64-03-PLAN.md Step 6`.

### 8.1 Revert on throwaway worktree

```
NEEDS_OPERATOR: paste
  git revert --no-edit <64-03-sha>
```

### 8.2 Post-revert import + test check

Both MUST exit 0 without `ImportError`:

```
NEEDS_OPERATOR: python -c "from cart.vkusvill_api import VkusVillCart; print('ok')"
NEEDS_OPERATOR: python -m pytest tests/ -q
```

### 8.3 Post-revert smoke

```
NEEDS_OPERATOR: bash scripts/verify_v1.20.sh 64
```

Expect: 64-A + 64-C still PASS. 64-B state depends on which commit was reverted:
- If the GO commit was reverted, 64-B (URL is None) PASSes again.
- If only the flag-flip systemd config change was reverted but the code still has FAST_CART_ADD_URL populated, 64-B still fails the "is None" check; that is the signal to revert the code commit too.

Rollback rehearsal outcome: `NEEDS_OPERATOR` (PASS / FAIL)

---

## 9. Merge Decision

| Gate | Status |
|---|---|
| Local implementation (64-01 + 64-02) | PASS |
| HAR captured + Section B filled | NEEDS_OPERATOR |
| Live ablation + Section C filled | NEEDS_OPERATOR |
| Go/no-go decision documented (Section D) | NEEDS_OPERATOR |
| Payload trimmed (Section E) | NEEDS_OPERATOR |
| If GO: swap implemented + tests added | NEEDS_OPERATOR |
| EC2 deploy + smoke 3/3 | NEEDS_OPERATOR |
| Live p95 gate | NEEDS_OPERATOR |
| Rollback rehearsed | NEEDS_OPERATOR |
| v1.19 regression 24/24 | NEEDS_OPERATOR |

Merge allowed when all rows above are PASS. Operator sign-off: `NEEDS_OPERATOR` (name + UTC timestamp).

---

*Verification: 64-VERIFICATION.md*
*Created (skeleton): 2026-05-10 - fill during 64-03 execution*

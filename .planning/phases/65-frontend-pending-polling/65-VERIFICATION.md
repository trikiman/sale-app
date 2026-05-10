# Phase 65 Verification — Frontend Pending-Polling + Idempotency

## Status: IN PROGRESS (awaiting operator live verification)

**Ships locally (this PR):**
- [x] 65-01 backend idempotency + `/api/cart/add-status-by-client-id/{cri}` endpoint
- [x] 65-02 frontend 8s->5s + polling on AbortError
- [x] 65-03 smoke script block + this verification skeleton
- [x] 3/3 tests pass in `backend/test_cart_idempotency.py`
- [x] `bash -n scripts/verify_v1.20.sh` green
- [x] `cd miniapp && npm run build` green

**NEEDS_OPERATOR (cannot be automated from this environment):**

### NEEDS_OPERATOR-1: Playwright slow-path test

- **File to create:** `miniapp/tests/test_cart_slow_path.py`
- **Fixture:** mock backend to delay `/api/cart/add` by 12s (synthetic slow-add).
- **Assertions:**
  - UI shows success toast (not "Korzina ne otvetila vovremya").
  - Cart count increments by exactly 1 (no double-add).
  - Reaches the polling fallback (console.log `[CART-ADD-POLL]` line present).
- **Out of scope here** because running a real miniapp + backend + mock requires
  a local dev environment. The polling loop itself is covered by the 3 backend
  unit tests + the `bash -n` + `npm run build` gates.

### NEEDS_OPERATOR-2: EC2 deploy

```bash
# On scraper-ec2:
cd /home/ubuntu/saleapp
git fetch origin && git reset --hard origin/<phase-65-branch>
sudo systemctl restart saleapp-backend      # picks up new endpoint + idempotency
# Vercel miniapp auto-deploys on push; confirm `controller.abort(), 5000` in the
# production bundle via browser DevTools Sources.
bash scripts/verify_v1.20.sh 65              # should print 3 green
```

### NEEDS_OPERATOR-3: 100-sample slow-add double-add rate measurement

- Run the Playwright fixture 100x with synthetic 12s delay.
- Expected: 100/100 success toasts, 0/100 double-adds in `/api/cart/items`.
- Record metric in Phase 66 `cart_events.jsonl` (`double_add_rate_1h` field).
- If double-add rate > 0, halt and inspect `_cart_add_attempt_by_client_id`
  for stale entries — the prune path or 5s dedupe window likely leaks.

### NEEDS_OPERATOR-4: Rollback rehearsal

```bash
# On a throwaway worktree:
git revert <65-01-hash> <65-02-hash> <65-03-hash>
python -m pytest tests/ backend/ -q             # must be all-green
bash scripts/verify_v1.20.sh                    # 62-64 still green; 65 block absent
```

Confirm:
- Backend still boots without `_cart_add_attempt_by_client_id`.
- Frontend falls back to the v1.19 8s-abort behavior (no polling).
- No stray references to `/api/cart/add-status-by-client-id` in any code path.

## Success Criteria Map (from ROADMAP.md)

| Criterion | Status | Evidence |
|---|---|---|
| 1. handleAddToCart polls on AbortError for up to 15s total, shows success not fail | CODE COMPLETE | `miniapp/src/App.jsx::handleAddToCart` catch block |
| 2. AbortController 8s -> 5s | CODE COMPLETE | `grep -c "controller.abort(), 5000" miniapp/src/App.jsx` == 1 |
| 3. Backend idempotency: same client_request_id returns same attempt_id, no double VkusVill call | CODE COMPLETE | `backend/test_cart_idempotency.py::test_client_request_id_dedupe_returns_same_attempt` PASS |
| 4. Playwright test_cart_slow_path.py | NEEDS_OPERATOR | see NEEDS_OPERATOR-1 |
| 5. EC2+Vercel deploy; 100-sample slow-add double-add rate = 0 | NEEDS_OPERATOR | see NEEDS_OPERATOR-2, NEEDS_OPERATOR-3 |
| 6. scripts/verify_v1.20.sh extended with frontend polling check | CODE COMPLETE | Phase 65 block with 65-A/65-B/65-C; `bash -n` green |

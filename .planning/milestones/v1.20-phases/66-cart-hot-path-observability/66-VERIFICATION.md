# Phase 66 Verification — Cart Hot-Path Observability

## Status: IN PROGRESS (awaiting operator live verification)

**Ships locally (this PR):**
- [ ] 66-01 /api/health/deep cart_add block (OBS-04) + 5 tests
- [ ] 66-02 data/cart_events.jsonl 11-key ledger (OBS-05) + 2 tests
- [ ] 66-03 scripts/verify_v1.20.sh Phase 66 block + this verification skeleton
- [ ] 7/7 tests pass in backend/test_cart_obs.py
- [ ] bash -n scripts/verify_v1.20.sh green
- [ ] cd miniapp && npm run build green (sanity; no frontend change)

**NEEDS_OPERATOR (cannot be automated from this environment):**

### NEEDS_OPERATOR-1: EC2 deploy

```bash
cd /home/ubuntu/saleapp
git fetch origin && git reset --hard origin/main
sudo systemctl restart saleapp-backend
sudo systemctl status saleapp-backend --no-pager
bash scripts/verify_v1.20.sh 66
```

### NEEDS_OPERATOR-2: 50-sample synthetic cart-add p95 baseline

Run 50 cart-add attempts against a healthy linked user on EC2 and confirm p95 <= 4.0 s (inherited from Phase 63/64 baseline). Phase 66 is pure-observability — if p95 regresses, the cause is the per-attempt detector overhead, not the block compute on /api/health/deep.

```bash
cd /home/ubuntu/saleapp
python3 - <<'PY'
import time, statistics, requests
USER_ID = "<real-linked-telegram-user-id>"
PRODUCT_ID = 731
URL = "http://127.0.0.1:8000/api/cart/add"
HEADERS = {"Content-Type":"application/json","X-Telegram-User-Id": str(USER_ID)}
durations = []
for i in range(50):
    body = {"user_id": USER_ID, "product_id": PRODUCT_ID, "is_green": False, "allow_pending": True, "client_request_id": f"p66-smoke-{i}-{int(time.time())}"}
    t0 = time.monotonic()
    r = requests.post(URL, json=body, headers=HEADERS, timeout=15)
    durations.append(int((time.monotonic()-t0)*1000))
    time.sleep(0.4)
qs = statistics.quantiles(sorted(durations), n=100)
print(f"p50={int(qs[49])}ms p95={int(qs[94])}ms p99={int(qs[98])}ms max={max(durations)}ms")
PY
```

Record actual p50/p95/p99:
- p50: ____ ms
- p95: ____ ms (pass if <= 4000)
- p99: ____ ms
- max: ____ ms

### NEEDS_OPERATOR-3: External /api/health/deep includes cart_add block

After NEEDS_OPERATOR-2 populates the ledger:

```bash
curl -sS https://<public-domain>/api/health/deep | python3 -m json.tool
```

Confirm:
- [ ] cart_add key present
- [ ] All 8 sub-keys present (p50_ms, p95_ms, p99_ms, success_rate_1h, success_rate_24h, double_add_rate_1h, window_sample_1h, window_sample_24h)
- [ ] window_sample_1h >= 40
- [ ] p95_ms matches NEEDS_OPERATOR-2 within ~10%
- [ ] If p95_ms > 6000, status is "degraded"; if > 12000, eligible for "unhealthy" per OBS-02 severity map.

### NEEDS_OPERATOR-4: data/cart_events.jsonl schema in the wild

```bash
tail -n 3 /home/ubuntu/saleapp/data/cart_events.jsonl | python3 -c '
import sys, json
for ln in sys.stdin:
    d = json.loads(ln)
    required = {"timestamp_iso","user_id_hash","attempt_id","product_id","duration_ms","success","error_type","client_request_id","sessid_age_s","warmup_hit","concurrent_recalc"}
    missing = required - set(d.keys())
    extra = set(d.keys()) - required
    print("OK" if not missing and not extra else f"BAD: missing={missing} extra={extra}")
'
```

Confirm:
- [ ] 3 "OK" lines printed
- [ ] user_id_hash is 12 hex chars
- [ ] warmup_hit is true for at least some attempts
- [ ] concurrent_recalc is true for at least some attempts
- [ ] sessid_age_s is a reasonable int for linked users, null otherwise

### NEEDS_OPERATOR-5: Rollback rehearsal

```bash
git revert <66-01-hash> <66-02-hash> <66-03-hash>
python3 -m pytest backend/ tests/ -q
bash -n scripts/verify_v1.20.sh
bash scripts/verify_v1.20.sh 62
bash scripts/verify_v1.20.sh 63
bash scripts/verify_v1.20.sh 64
bash scripts/verify_v1.20.sh 65
```

Confirm:
- [ ] Backend boots without the new helpers.
- [ ] No stray references to _compute_cart_add_block, _emit_cart_event, or _CART_EVENTS_PATH.
- [ ] data/cart_events.jsonl stops growing.
- [ ] /api/health/deep body has no cart_add key.

### NEEDS_OPERATOR-6: v1.19 regression gate (cross-version)

```bash
bash scripts/verify_v1.19.sh all
# Expect: 24/24 green
```

## Success Criteria Map (from ROADMAP.md Phase 66)

| Criterion | Status | Evidence |
|---|---|---|
| 1. /api/health/deep cart_add block with 8 fields | CODE | 66-01 _compute_cart_add_block + snapshot integration |
| 2. data/cart_events.jsonl 11-key schema per attempt | CODE | 66-02 _emit_cart_event at every terminal branch |
| 3. p95 > 6000 -> degraded; > 12000 -> unhealthy | CODE | 66-01 D7 reasons wiring |
| 4. External curl /api/health/deep returns 200 with cart_add.p95_ms populated when traffic exists | NEEDS_OPERATOR | NEEDS_OPERATOR-3 |
| 5. scripts/verify_v1.20.sh total smoke checks >= 20 green | CODE | 66-A/B/C added |
| 6. Per-phase latency baselines 62-65 retained as regression gates | CODE | Phase 62/63/64/65 smoke blocks unchanged |

## Phase 66 Ledger Notes

- `_cart_add_attempts` TTL is 30 s (`_CART_PENDING_ATTEMPT_TTL_SECONDS = 30.0`). `p95_1h` therefore reflects ~the last 30 s of traffic at most; the field name is aspirational. If stricter 1 h accuracy is needed, a future phase should lift the TTL or persist resolved attempts to a bounded ring buffer. Acceptable for v1.20 because:
  - Live operator use cares about "right now is latency bad?" — which the 30-sec-ish window answers.
  - Post-mortem use cares about the JSONL ledger, which has no TTL.
- `warmup_hit` compares monotonic clocks within the same process. If the backend restarts, the field becomes `false` for ~5 min until the next scheduler cycle fires — correct semantics (the warmup state is genuinely unknown right after restart).
- `concurrent_recalc` is a LAGGING indicator (captured at cart-add start). A poll arriving AFTER cart-add start is not flagged — that race is phase-63-deduped to the cache and never actually races `basket_recalc.php`. Present semantics: "did this cart-add start alongside a prior pending for the same user?".

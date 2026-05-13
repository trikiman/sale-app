# Phase 66 — Cart Hot-Path Observability — Context

**Milestone:** v1.20 Cart-Add Latency & User-Facing Responsiveness
**Phase number:** 66
**Phase slug:** cart-hot-path-observability
**Date captured:** 2026-05-12
**Requirements covered:** OBS-04, OBS-05 + continuing OPS-09/10/11

---

## Domain

Close v1.20 by making cart-add latency regressions visible to the same uptime monitor that watches v1.19's pool + breaker, and make every cart-add anomaly post-mortem-able through a structured ledger.

1. **OBS-04** — `/api/health/deep` response gains an optional `cart_add` block derived from the existing `_cart_add_attempts` ledger. Fields: `p50_ms`, `p95_ms`, `p99_ms`, `success_rate_1h`, `success_rate_24h`, `double_add_rate_1h`. When the last hour has zero attempts the block is omitted (not a 503 condition — zero attempts at 3am is healthy).
2. **OBS-05** — Every `/api/cart/add` attempt appends one JSON line to `data/cart_events.jsonl` capturing a 10-key schema (`user_id_hash`, `attempt_id`, `product_id`, `duration_ms`, `success`, `error_type`, `client_request_id`, `sessid_age_s`, `warmup_hit`, `concurrent_recalc`). Privacy preserved via `sha256(user_id)[:12]`.

Together these give the operator a dashboard signal (p95 spike) and a forensic trail (which attempts drove the spike, and what their hot-path state was).

---

## SPEC Lock (from REQUIREMENTS.md OBS-04/05 and ROADMAP.md Phase 66)

LOCKED — planner must NOT re-litigate:

- **OBS-04 data source:** Existing `_cart_add_attempts: dict[str, dict]` in `backend/main.py` (ledger already populated by `_get_or_create_pending_cart_attempt` + `_update_cart_add_attempt`). No new ledger. No persistence.
- **OBS-04 rolling window:** p50/p95/p99 over last 1 h of `resolved_at` timestamps; `success_rate_1h` over last 1 h; `success_rate_24h` over last 24 h; `double_add_rate_1h` over last 1 h. The TTL on `_cart_add_attempts` is 30 s so the 1 h / 24 h windows are computed from whatever the process has seen since boot — the ledger is in-memory only. Pre-boot history is not recovered (acceptable per OBS-04: "optional block", "computed from ledger").
- **OBS-04 double-add heuristic:** Same `user_id` + `product_id` + both `status=="success"` + `resolved_at` delta <= 30 s. Matches ROADMAP.md Phase 66 success criterion 1 exactly.
- **OBS-04 degraded/unhealthy thresholds:** Per ROADMAP.md Phase 66 criterion 3: `cart_add.p95_ms > 6000` for last 1 h flips deep-health to `degraded`; `> 12000` flips to `unhealthy`. These reasons extend the existing `reasons[]` list without breaking the OBS-02 schema.
- **OBS-04 zero-traffic handling:** If last 1 h has zero attempts -> `cart_add` block omitted entirely (not a 503). Status reasons list is unchanged.
- **OBS-05 JSONL path:** `data/cart_events.jsonl` (NEW stream, separate from `data/proxy_events.jsonl` and `data/warmup_events.jsonl`). Append-only. Best-effort writes — disk failure MUST NOT block cart-add.
- **OBS-05 hash algo:** `hashlib.sha256(str(user_id).encode("utf-8")).hexdigest()[:12]`. Matches the convention already published as `keepalive.warmup.hash_user_id` — reuse that import directly.
- **OBS-05 schema:** Exactly 10 keys plus a leading `timestamp_iso` (ISO-8601 UTC). Keys: `timestamp_iso`, `user_id_hash`, `attempt_id`, `product_id`, `duration_ms`, `success`, `error_type`, `client_request_id`, `sessid_age_s`, `warmup_hit`, `concurrent_recalc`.
- **OBS-05 emission point:** One line per resolved attempt, written at the end of `cart_add_endpoint` (all terminal branches — success, failed, auth_expired, product_gone, timeout, transient, pending_timeout, dedupe_hit, exception). Guarded by a single helper `_emit_cart_event(...)` so the emit site is singular.
- **OPS-09 smoke:** 3 new checks (66-A..66-C) in `scripts/verify_v1.20.sh`.
- **OPS-10 regression gate:** cart-add p95 <= 4.0 s on EC2 (Phase 66 doesn't change latency; gate inherits from Phase 63/64 baseline).
- **OPS-11 rollback rehearsal:** mandatory before merge.

---

## Decisions

### D1. warmup_hit detection — monotonic-ts freshness check

`keepalive.warmup._LAST_WARMUP_AT` keeps `user_id_hash -> monotonic_ts` of the last warmup (successful OR failed, because it's anti-spam-protected either way). For each cart-add we check: was this user's last warmup within the last 300 s (5 min)?

- 5 min covers both the 15 min scheduler cycle that has just fired AND the on-app-open nudge that fires <= 500 ms before the first tap. If the user tapped with a hot sessid the cart-add reaped the benefit; `warmup_hit=true`.
- Outside 5 min the field is `false` — the hot path paid the cold-sessid revalidation tax.
- Read is non-blocking under `_STATE_LOCK`. If the lookup raises (impossibly bad state) we fall through to `false`.

### D2. concurrent_recalc detection — ledger peek at cart-add start

At the instant `cart_add_endpoint` begins (immediately after `_validate_user_header`), we peek at `_cart_add_attempts` for ANY entry belonging to this `user_id` with `status=="pending"` whose `started_at` is within the last 12 s (matches PERF-06 cache TTL). If yes, `concurrent_recalc=true`. This answers "did this cart-add race a `/api/cart/items` poll on the same user?".

- Semantics match ROADMAP.md Phase 66 OBS-05 "`concurrent_recalc` (bool)" — the field name refers to the race with `basket_recalc.php` that PERF-06 eliminated. True means the attempt raced a poll that Phase 63 deduped.
- Read is non-blocking under `_cart_add_attempts_lock`.

### D3. sessid_age_s source

Read the sessid file directly via the existing cookies-path resolver. `VkusVillCart._sessid_ts` is only populated after `__enter__`/auth work, which is inside the hot path. We don't want to block on that — instead peek at the JSON file's `sessid_ts` key (stored by `_persist_session_metadata`):

```python
def _read_sessid_age_seconds(user_id: str) -> int | None:
    try:
        cookies_path = _resolve_cart_cookies_path(user_id)
        with open(cookies_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        ts = data.get("sessid_ts")
        return int(time.time() - float(ts)) if ts else None
    except Exception:
        return None
```

If the file is missing / malformed / has no `sessid_ts` -> `None`, which JSON-encodes as `null`. Callers interpret `null` as "unknown".

### D4. JSONL rotation

Not in scope for this phase. ROADMAP.md Phase 66 says "single structured JSONL line per attempt". Rotation can be handled by systemd `logrotate` with `copytruncate` at a later ops phase (matches how `warmup_events.jsonl` and `proxy_events.jsonl` are treated today — no in-process rotation).

### D5. Double-add heuristic uses `resolved_at` not `started_at`

`resolved_at` is stamped in `_update_cart_add_attempt` when `status` transitions from `pending` to a terminal state. Using `resolved_at` ensures we're comparing when VkusVill actually confirmed, not when our backend started processing. Two successful adds resolving 18 s apart count as one double-add; two starting 18 s apart but resolving 35 s apart do not.

### D6. Latency percentile computation

Use `statistics.quantiles(..., n=100)` on the `duration_ms` values in the window. For samples <= 2 we fall back to `min/max/max`. Computation runs on each `/api/health/deep` call — acceptable because:

- Ledger size is bounded: 30 s TTL times typical traffic (< 1 req/s) is < 30 entries. Even in a 1 h window the ledger remains small because entries expire at 30 s; `p95_1h` effectively means "p95 of whatever remains in the ledger that happens to have resolved within the last hour". Given the 30 s TTL, this is approximately "p95 over the last 30 s" — which is what the operator actually wants for a live health check.
- 1 req/s times 3600 s = 3600 data points maximum if TTL were lifted — still sub-ms to compute.

### D7. Percentile extension into health status

Per ROADMAP.md Phase 66 criterion 3:

- If `cart_add.p95_ms > 6000` for last 1 h -> add reason `cart_add_p95_high:{p95}ms` to `reasons[]` (degraded).
- If `cart_add.p95_ms > 12000` -> add reason `cart_add_p95_critical:{p95}ms` (unhealthy via severity count).

Only emit ONE cart_add latency reason at a time:
- `cart_add.p95_ms > 12000` -> `reasons.append("cart_add_p95_critical:{p95}ms")` AND skip the >6s reason
- `cart_add.p95_ms > 6000` (but <= 12000) -> `reasons.append("cart_add_p95_high:{p95}ms")`
- `cart_add.p95_ms <= 6000` -> nothing added

---

## Locked Defaults

- `CART_EVENTS_PATH = os.path.join(BASE_DIR, "data", "cart_events.jsonl")` in `backend/main.py` (or new `cart/events.py` helper — either location acceptable; single module-level constant).
- `_HEALTH_CART_ADD_DEGRADED_P95_MS = 6000`, `_HEALTH_CART_ADD_UNHEALTHY_P95_MS = 12000` as module-level constants in `backend/main.py`.
- `_CART_EVENT_WARMUP_FRESHNESS_S = 300.0` for D1.
- `_CART_EVENT_CONCURRENT_RECALC_WINDOW_S = 12.0` for D2 (matches PERF-06 TTL intentionally).
- Double-add window: 30 seconds.
- Rolling windows: 3600 s (1 h) for p50/p95/p99 + success_rate_1h + double_add_rate_1h; 86400 s (24 h) for success_rate_24h.

---

## Files Modified

- `backend/main.py`:
  - `_build_reliability_snapshot` extended: after existing body, computes `cart_add` block from `_cart_add_attempts`; appends to `snapshot`. Appends p95 reasons as per D7.
  - `cart_add_endpoint` instrumented: at start, snapshot `sessid_age_s` via helper + `warmup_hit` + `concurrent_recalc`. On every terminal branch, call `_emit_cart_event(...)` before `return`. Exception handler emits too.
  - New helpers: `_emit_cart_event`, `_read_sessid_age_seconds`, `_compute_cart_add_block`, `_warmup_hit_for_user`, `_has_concurrent_recalc`.
  - New constant: `CART_EVENTS_PATH`.
- `backend/test_cart_obs.py` (NEW):
  - `test_cart_events_jsonl_schema_success` — cart-add success emits 10-key line.
  - `test_cart_events_jsonl_schema_failed` — failed attempt emits `success=false, error_type=...`.
  - `test_cart_add_block_p95_p99_computation` — synthetic 100 attempts -> p50/p95/p99 math correct.
  - `test_cart_add_block_zero_traffic_omits_block` — empty ledger -> `cart_add` key absent.
  - `test_cart_add_block_double_add_rate` — two same-(user,product) successes 20s apart -> rate == 1.0.
  - `test_cart_add_block_p95_degrades_health` — synthetic p95=7000 -> `cart_add_p95_high` in reasons.
  - `test_cart_add_block_p95_critical` — synthetic p95=13000 -> `cart_add_p95_critical` in reasons.
- `scripts/verify_v1.20.sh`:
  - New `Phase 66` block with 66-A (helpers importable + constants), 66-B (`/api/health/deep` returns 200 with `cart_add` block when traffic exists — smoke triggers one attempt first), 66-C (data/cart_events.jsonl has valid 11-key schema in last line when present).
- `.planning/phases/66-cart-hot-path-observability/`:
  - `66-CONTEXT.md` (this file)
  - `66-01-PLAN.md` — OBS-04 `/api/health/deep` cart_add block + degraded/unhealthy reasons + 5 tests
  - `66-02-PLAN.md` — OBS-05 JSONL emit + 10-key schema + helpers + 2 tests
  - `66-03-PLAN.md` — smoke-script Phase 66 block + VERIFICATION skeleton + v1.19 regression check
  - `66-VERIFICATION.md` — with NEEDS_OPERATOR sections for EC2 deploy + p95 regression + rollback rehearsal

---

## Verification

- **Local (this session):**
  - 7 new pytest cases in `backend/test_cart_obs.py` all green.
  - Full suite green (>= 313 passed, 3 Windows-only pre-existing failures unchanged).
  - `bash -n scripts/verify_v1.20.sh` green.
  - `cd miniapp && npm run build` green (no frontend change, sanity only).

- **NEEDS_OPERATOR (66-VERIFICATION.md):**
  - EC2 deploy + `systemctl restart saleapp-backend`.
  - 50-sample synthetic cart-add on EC2; assert p95 <= 4.0 s (inherits Phase 63/64 baseline).
  - External `curl https://api.vkusvillsale.example/api/health/deep` returns 200 with `cart_add.p95_ms` populated when traffic exists.
  - `tail -n 3 data/cart_events.jsonl` on EC2 shows valid 11-key JSON per line.
  - Rollback rehearsal: `git revert` the 3 commits, `pytest -q` green, `bash -n scripts/verify_v1.20.sh` green, `cart_events.jsonl` stops growing.
  - `bash scripts/verify_v1.19.sh all` still 24/24 green (cross-version regression gate).

---

## Phase Boundary

**Ships:** `/api/health/deep` `cart_add` block + degraded/unhealthy extension + `data/cart_events.jsonl` 11-key schema + 7 unit tests + 3 smoke checks + VERIFICATION skeleton.

**Does NOT ship:**
- JSONL rotation (deferred to ops phase; systemd `logrotate` is the ops path).
- Historical latency backfill (in-memory ledger only; no Redis/SQLite ledger).
- Frontend observability wiring (UX-01/02/03 already shipped in Phase 65).
- Admin dashboard UI for `cart_add` block (OBS-FUT-02 in v2 requirements).

**Acceptance gate:** `cart_add` block appears in `/api/health/deep` when traffic exists + 7/7 tests green + 3/3 Phase-66 smoke checks green + 24/24 v1.19 + rollback rehearsed + cart-add p95 <= 4.0 s on EC2 (inherited).

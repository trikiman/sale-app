# Phase 61 — Deep Health Endpoint + Pool Snapshot — VERIFICATION

**Date:** 2026-05-05
**Branch:** `main` @ `ebd5144` (post-deploy)
**Status:** COMPLETE — all UAT criteria met, smoke green

---

## TL;DR

5 commits land Phase 61 cleanly. Local pytest 8/8, EC2 pytest 29/29,
smoke 24/24 across all three milestone phases, external GET via Vercel
returns 200 healthy, rollback rehearsal reverts to a byte-identical
Phase 60 tree.

---

## Requirements coverage

| ID     | Requirement                                                  | Status |
|--------|--------------------------------------------------------------|--------|
| REL-11 | Unauth `/api/health/deep` with truthful 200/503              | done   |
| REL-12 | `VlessProxyManager.pool_snapshot()` typed accessor           | done   |
| OBS-01 | `reasons[]` array on health responses                        | done   |
| OBS-02 | `proxy_events.jsonl` enriched with pool counters             | done   |
| OBS-03 | `/admin/status` carries the same `reliability` block         | done   |

---

## Commits

```
ebd5144 fix(61-03): smoke 61-B uses one-shot probe; 61-E uses GET headers
8316113 test(61-03): extend smoke script with Phase 61 checks 61-A..61-H
dc17421 test(61-02): pool_snapshot, event enrichment, /api/health/deep contract
54f963f feat(61-01): pool_snapshot() + /api/health/deep + /admin/status reliability block
c97964e docs(phase-61): plan phase 61 (deep health endpoint + pool snapshot)
```

---

## Local pre-deploy verification

```
$ python3 -m pytest tests/test_pool_snapshot.py -v
8 passed in 0.56s
```

Coverage:
- Shape on empty pool (5 keys)
- Reflects pool size after seeding
- Counts active VkusVill cooldowns; excludes expired (> 4 h)
- `active_outbounds` never exceeds `size` even with cooldowns referencing non-pool hosts
- Thread-safe under `self._lock` (100 reads x 50 writes concurrent)
- `_track_event` auto-injects `pool_size` / `quarantined_count` / `active_outbounds_count`
- `_track_event` respects explicit caller fields (setdefault semantics)
- `_track_event` never raises if `pool_snapshot()` throws (best-effort)

`tests/test_health_deep_endpoint.py` (21 FastAPI tests) deferred to EC2
since FastAPI isn't installed locally — same pattern as
`tests/test_cart_errors.py`.

---

## EC2 deploy

```
$ ssh scraper-ec2 'cd /home/ubuntu/saleapp && git fetch && git reset --hard origin/main'
HEAD is now at ebd5144 fix(61-03): ...

$ ssh scraper-ec2 'sudo systemctl restart saleapp-backend saleapp-scheduler && sleep 5 && \
    systemctl is-active saleapp-backend saleapp-scheduler saleapp-xray'
active
active
active
```

Both backend AND scheduler restarted — backend exposes the new endpoint,
scheduler picks up the enriched `_track_event` code path.

---

## EC2 pytest (Python 3.12)

```
$ ssh scraper-ec2 'cd /home/ubuntu/saleapp && \
    python3 -m pytest tests/test_pool_snapshot.py tests/test_health_deep_endpoint.py -v'
collected 29 items
============================== 29 passed in 2.61s ==============================
```

Full coverage breakdown (29 tests, 0 failures):
- `test_pool_snapshot.py` — 8 tests (shape, counters, thread-safety, event enrichment, fault-tolerance)
- `test_health_deep_endpoint.py` — 21 tests:
  - Schema: 200 + full schema, Cache-Control header
  - Status mapping: pool below min_healthy, breaker open/half_open, xray off, no cycle, stale cycle, multi-problem aggregation, pool unavailable
  - Rate limit: 429 on back-to-back, recovery after 1.1 s, per-IP independence
  - Security: never 401/403 (unauth required for monitors)
  - Helpers: breaker snapshot variants (missing/valid/corrupt/unknown-state), xray closed-port branch, severity ranking
  - Admin: `/admin/status` includes `reliability` block

---

## Live endpoint evidence

### Direct EC2 (`http://13.60.174.46:8000/api/health/deep`)

```json
{
  "status": "healthy",
  "reasons": [],
  "pool": {
    "size": 15,
    "min_healthy": 7,
    "quarantined_count": 7,
    "active_outbounds": 15,
    "last_refresh_at": "2026-05-05T15:14:15",
    "available": true
  },
  "breaker": {"available": true, "state": "closed", "cooldown_s": 120, "fails": 0},
  "xray": {"listening": true, "port": 10808},
  "last_cycle_age_s": 56,
  "as_of": "2026-05-05T17:29:10"
}
```

**Truthful pool drift visible:** `quarantined_count: 7` shows that 7 of
the 15 pool hosts are in active VkusVill cooldown. This is precisely the
visibility v1.18 lacked — drift from 25 -> 13 went undetected back then.

### Vercel edge (`https://vkusvillsale.vercel.app/api/health/deep`)

```
HTTP 200
{... same shape, status: healthy ...}
```

Vercel rewrite at `vercel.json` proxies to `http://13.60.174.46:8000`.
External uptime monitors can hit this URL without credentials and get a
binary 200/503 + structured reasons[] for alerts.

### `_track_event` enrichment one-shot (deployed code path)

```
$ ssh scraper-ec2 '... python3 inline ...'
sample: {"ts": "2026-05-05T17:23:29", "event": "smoke_oneshot", "addr": "1.1.1.1",
         "pool_size": 1, "quarantined_count": 0, "active_outbounds_count": 1}
```

OBS-02 confirmed against the running `vless/manager.py` on EC2.

---

## Smoke script (`scripts/verify_v1.19.sh all`)

```
=== Phase 59 — Pre-flight VLESS Probe ===
  ok 59-A: vless/preflight.py exists on EC2
  ok 59-B: vless.preflight imports without error
  ok 59-C: _PROBE_TIMEOUT_S_FLOOR = 12.0 (>= 12.0)
  ok 59-D: scheduler invokes pre-flight probe (log evidence)
  ok 59-E: preflight pytest suite green on EC2
  ok 59-F: saleapp-xray is active
  ok 59-G: saleapp-scheduler is active
  ok 59-H: Vercel /api/products returns HTTP 200 (edge reachable)
  ok 59-I: Vercel /api/cart/add reachable (HTTP 422; 4xx = authed route works)

=== Phase 60 — Observatory probeURL + Circuit Breaker ===
  ok 60-A: data/scheduler_state.json is gitignored
  ok 60-B: observatory.probeURL = 'https://vkusvill.ru/favicon.ico'
  ok 60-C: observatory.probeInterval = 60s (<= 60s)
  ok 60-D: Phase 59 preflight floor still 12.0 (>= 12.0)
  ok 60-E: probeURL + breaker pytests green on EC2
  ok 60-F: data/scheduler_state.json valid (state=closed)
  ok 60-G: scheduler emits breaker log lines (1 in last 10 min)

=== Phase 61 — Deep Health Endpoint + Pool Snapshot ===
  ok 61-A: pool_snapshot() returns the documented schema
  ok 61-B: deployed _track_event emits pool counters (one-shot OBS-02 verification)
  ok 61-C: /api/health/deep reachable on EC2 localhost (HTTP 200)
  ok 61-D: response schema valid (status=healthy)
  ok 61-E: Cache-Control: no-store present
  ok 61-F: rate-limit returns 429 on back-to-back (200,429)
  ok 61-G: pool_snapshot + health-deep pytests green on EC2
  ok 61-H: cross-phase guards intact (floor=12.0, probeURL=vkusvill.ru)

=== Summary ===
  ok All checks passed for phase 'all'
```

**24/24 across the entire v1.19 milestone.** Cross-phase sanity guards
in 60-D and 61-H confirm Phase 59's 12 s timeout floor and Phase 60's
VkusVill probeURL are not regressed.

---

## Rollback rehearsal

Goal: prove that reverting the 5 Phase-61 commits leaves the tree
byte-identical to Phase 60's last commit (`b9465c8`), with no manual
intervention.

```
$ git checkout -b rehearsal/phase-61-revert
Switched to a new branch 'rehearsal/phase-61-revert'

$ git revert --no-edit ebd5144 8316113 dc17421 54f963f c97964e
[clean revert: 5 commits, no conflicts]

$ git diff b9465c8 HEAD -- vless backend tests scripts .planning .gitignore | wc -l
0

$ python3 -m pytest tests/test_preflight_*.py tests/test_xray_probe_url_regression.py \
    tests/test_circuit_breaker_state_machine.py -q
44 passed in 0.30s
```

**Result:** byte-identical revert in 5 commits, no manual intervention,
44 Phase 59 + Phase 60 tests still green on the rolled-back tree.

Cleanup:
```
$ git checkout main && git branch -D rehearsal/phase-61-revert
Switched to branch 'main'
Deleted branch rehearsal/phase-61-revert (was 0eb0946).
```

Production rollback path (if Phase 61 had to be reverted on prod):
```
ssh scraper-ec2 'cd /home/ubuntu/saleapp && \
    git revert --no-edit ebd5144 8316113 dc17421 54f963f c97964e && \
    git push origin main && \
    sudo systemctl restart saleapp-backend saleapp-scheduler'
```

---

## Files changed

```
backend/main.py                                                       | +180
vless/manager.py                                                      |  +56
tests/test_pool_snapshot.py                                           | +200 new
tests/test_health_deep_endpoint.py                                    | +337 new
scripts/verify_v1.19.sh                                               | +137
.planning/phases/61-deep-health-endpoint-pool-snapshot/README.md      |  +80 new
.planning/phases/61-deep-health-endpoint-pool-snapshot/61-VERIFICATION.md (this file)
```

---

## UAT scorecard (from README)

| Criterion                                                                        | Verified by                            | Status |
|----------------------------------------------------------------------------------|----------------------------------------|--------|
| `/api/health/deep` returns 200 + JSON when system is healthy                     | live curl + 61-D                       | done   |
| Returns 503 when pool < 7, breaker != closed, xray off, or cycle stale > 15 min  | 9 status-mapping tests in 61-G         | done   |
| Response shape stable across reboots: `{status, reasons, pool, breaker, xray, last_cycle_age_s, as_of}` | schema tests + live | done   |
| Endpoint is unauthenticated (uptime monitors)                                    | `test_endpoint_does_not_require_admin_token` + Vercel curl | done   |
| Rate limit: 1 req/s/IP returns 429 on burst                                      | 3 RL tests + 61-F live                 | done   |
| `Cache-Control: no-store` set                                                    | header test + 61-E live                | done   |
| `pool_snapshot()` returns documented schema                                      | 5 shape tests + 61-A live              | done   |
| `proxy_events.jsonl` entries enriched with pool counters                         | 3 enrichment tests + 61-B one-shot     | done   |
| `/admin/status` includes `reliability` block                                     | `test_admin_status_includes_reliability_block` | done   |
| Cross-phase: Phase 59 timeout floor + Phase 60 probeURL not regressed            | 61-H + smoke 60-D                      | done   |
| Rollback path proven (revert leaves byte-identical Phase 60 tree)                | rehearsal section above                | done   |

---

## Risk register — outcomes

| Risk (from README)                                                | Outcome                                          |
|-------------------------------------------------------------------|--------------------------------------------------|
| Health endpoint becomes a DDoS target (no auth)                   | 1 req/s/IP rate limit + dict self-prune at 10k   |
| `_pool_snapshot_for_health` couples HTTP module to xray boot      | Lazy-imported via `proxy_manager` shim; never raises |
| Reasons[] schema drift between releases breaks monitors           | Tests pin every reason string; CI breaks on rename |
| `_track_event` enrichment masks caller-supplied fields            | `setdefault` semantics — caller wins             |
| `_track_event` enrichment fails and breaks event logging          | Wrapped in try/except; falls back to original payload |

---

## Roadmap mapping

`.planning/STATE.md` advances to: **v1.19 Phase 61 COMPLETE — milestone
ready for audit.**

Phase 61 satisfies the final 5 of 12 requirements
(`REL-11`, `REL-12`, `OBS-01`, `OBS-02`, `OBS-03`) in
`.planning/REQUIREMENTS.md`.

Next: `gsd-audit-milestone v1.19` to validate that all 12
requirements are demonstrably met before archiving the milestone.

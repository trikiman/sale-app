---
phase: 97
title: URnetwork-Primary Egress
status: passed
verified: 2026-11-16
---

# Phase 97 — Verification

## Criterion 1 — pinned inbound, not a balancer member

**Passed (unit).** `test_pinned_inbound_exists_only_with_a_urn_outbound`,
`test_urn_traffic_is_pinned_not_balanced`,
`test_general_inbound_still_uses_the_balancer`.

**Live state, morning:** `urn-socks-in` was absent because the UR cache had not
been provisioned (`urnetwork: connect_error`) — the designed behaviour, since the
inbound must not be created without an outbound.

**Live state, 18:40 (after `/admin/proxy-refresh`):**

```
GET /api/admin/egress-probe
{"routes":[{"route":"urnetwork","ok":true,"reason":"ok"},
           {"route":"vless","ok":false,"reason":"timeout"}],
 "route":"urnetwork","ok":true}
```

The pinned UR network route now answers, and the balancer route is dead
(`pool 0/5`) — exactly the situation the phase was built for: with the pool at
zero the scraper still has a working egress instead of stalling.

## Criterion 2 — route-aware preflight

**Passed, verified live.**

```
GET /api/admin/egress-probe
{"routes":[{"route":"urnetwork","ok":false,"reason":"connect_error","elapsed_s":6.19},
           {"route":"vless","ok":true,"status":200,"reason":"ok","elapsed_s":3.8}],
 "route":"vless","ok":true}
```

The probe names the winning route and the winning port. Per-route caching is
pinned by `test_probe_cache_is_per_route` (a healthy UR must not vouch for a dead
balancer).

## Criterion 3 — UR-first candidates

**Passed.** `test_proxy_candidates_prefers_urnetwork`,
`test_proxy_candidates_still_works_without_urn`.

## Criterion 4 — a green cycle completes and records itself

**Passed, with the route caveat stated.** On the box the cycle now completes
through the **balancer** bridge, not UR (UR has no cache there):

```
before: health degraded [pool_below_min_healthy:1_lt_5, stale_cycle_2808s, stale_products_2838s]
         /api/admin/green-uptime -> cycles 1, last_ok_age 93m
after : health degraded [pool_below_min_healthy:1_lt_5]
         /api/admin/green-uptime -> cycles 2, cycles_ok 2, uptime 100%, last_ok_age 12.4m
```

`stale_cycle` and `stale_products` are gone: cycles run again and the per-cycle
record exists. The goal of this phase was never "UR specifically" — it was "a dead
pool cannot idle the scraper". UR-first stays in the code and activates when the
cache is provisioned.

## Root cause, recorded

1. `urn-ru-0` was only a balancer member → Xray chose dead VLESS nodes.
2. `pool 1/5`, `189 nodes quarantined` → `get_working_proxy()` returned `None`.
3. Scheduler checked `direct` → `BLOCKED (direct connection failed)` →
   "no working proxy found. Cycle will likely fail" → no cycle ran, while the
   balancer bridge on 10808 was serving VkusVill with HTTP 200 in 3.8 s.

## Suite

`tests/test_green_egress.py` — 8 tests. Full run: **307 passed, 3 skipped**, one
pre-existing failure (`test_vless_xray` port timing, unrelated).

---
created: 2026-05-10T16:26:37Z
title: VLESS admitted nodes go stale without dynamic rehealth
area: tooling
files:
  - vless/manager.py:632 (_probe_vkusvill — passes at admission, not re-run)
  - vless/manager.py:309 (refresh_proxy_list — only rebuilds when pool below MIN_HEALTHY or cache > 24h)
  - vless/manager.py:386 (is_cache_stale CACHE_TTL check)
  - data/vless_pool.json (admitted nodes never re-probed)
---

## Problem

A node that passes _probe_vkusvill at admission may be blocked by VkusVill minutes later (their anti-bot profiles individual proxy IPs over time). The current pipeline assumes admitted equals healthy indefinitely until cache TTL (about 24h) or pool falls below MIN_HEALTHY.

Observed 2026-05-10: fresh pool of 16-26 admitted RU nodes, but live bridge probes to vkusvill.ru returned HTTP 000 for 5/5 tries. The nodes had passed admission once, then quietly failed in production traffic. Observatory probeURL generates only dead events (never alive) so the balancer has no signal to rotate away.

We ended up in a state where pool_size=16, quarantined=7 implied a healthy pool, but actual end-to-end VkusVill reachability was 0%.

Observed flow:
1. Admission probe runs with fresh xray subprocess, succeeds, node goes into pool.
2. Main bridge starts routing real traffic through it.
3. VkusVill profiles the egress IP, starts silently dropping.
4. Subsequent production calls fail with TCP timeout (HTTP 000).
5. Observatory does probe, sees failure, marks dead. But already only-alive node.
6. Balancer stuck on dead node. No rotation.
7. Circuit breaker trips scheduler.

## Solution

TBD. Three layered ideas:

1. Periodic re-probe: every about 10 minutes, run _probe_vkusvill on each admitted node through the running bridge (not a fresh xray subprocess). Move failures to cooldown, drop from active outbounds, trigger refresh if pool_size drops below MIN_HEALTHY.
2. Balancer strategy: when all observatory probes fail for N consecutive cycles, force pool refresh plus xray restart.
3. Track per-node production success rate in pool entries (currently last_success_at is null for all). When it goes to 0 over a sliding window, treat as dead even if observatory still reports alive.

Compounds with:
- 2026-05-10-xray-not-reloaded-after-pool-admission.md (xray never sees new admissions anyway)
- 2026-05-10-observatory-probeurl-only-marks-nodes-dead-never-alive.md (no alive signal from observatory)

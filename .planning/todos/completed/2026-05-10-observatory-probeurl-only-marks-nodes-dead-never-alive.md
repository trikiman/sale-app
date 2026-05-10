---
created: 2026-05-10T16:26:37Z
title: observatory probeURL only marks nodes dead, never alive
area: tooling
files:
  - vless/config_gen.py:158 (probeURL = https://vkusvill.ru/favicon.ico)
  - bin/xray/configs/active.json (main-bridge observatory config)
  - bin/xray/logs/xray.stdout.log (observatory events)
---

## Problem

Only about 20 observatory events per day in xray.stdout.log and every single one is "node-X is dead". There is no matching "alive" event, ever.

Cadence mismatch too: probeInterval is configured as 60s but events land about 1 per hour. Either xray is suppressing duplicate states (seen the same dead many times, only first logged) or the probeURL target hangs so long the probes stack.

When every outbound is dead, leastPing has nothing to prefer. It collapses to effectively "pick the first one" — which is how we ended up routing all vkusvill.ru traffic to one broken node for days even after the pool gained 16+ new admitted nodes.

Separately there is a probe target mismatch: per-candidate admission probes use ipinfo.io egress + _probe_vkusvill (vkusvill.ru/ homepage), but the main running xray's observatory probes vkusvill.ru/favicon.ico. When the main bridge is handshaking fresh Reality connections through a bad node, favicon.ico hangs, observatory never sees a transition to up, the balancer never rotates.

## Solution

TBD. Three ideas to evaluate:

1. Use a probeURL simple and unrelated to VkusVill (like https://www.google.com/generate_204) so observatory measures node reachability, not VkusVill reachability. VkusVill-specific health stays in admission + circuit breaker.
2. Lower probeInterval and add explicit logging of "alive" transitions.
3. Add balancer-strategy fallback: if observatory marks all outbounds dead for more than N minutes, pick randomly rather than pinning to head-of-list.

Root cause of our 4-day stall was probably (3): observatory correctly marked the May-5 outbound dead, but with no others (before pool refresh started rewriting the file xray was not reading) there was no alternative to rotate to. Compounds with the xray-not-reloaded bug captured in 2026-05-10-xray-not-reloaded-after-pool-admission.md.

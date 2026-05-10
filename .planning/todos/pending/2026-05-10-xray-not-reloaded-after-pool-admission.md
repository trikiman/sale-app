---
created: 2026-05-10T16:26:37Z
title: xray bridge not reloaded after pool admission
area: tooling
files:
  - vless/manager.py:378 (_rebuild_and_restart_xray called but not reaching systemd service)
  - vless/manager.py:309 (refresh_proxy_list writes pool + rebuilds, doesn't trigger systemctl)
  - systemd/saleapp-xray.service (systemd-managed xray, PID persists across refreshes)
  - bin/xray/configs/active.json (gets rewritten by refresh, but running xray ignores it)
---

## Problem

Real root cause of the 4+ day scheduler outage (2026-05-06 10:19 to 2026-05-10 19:18 MSK).

The VLESS pool refresh pipeline on EC2 was working the whole time. Every ~1h it fetched upstream nodes, probed with live _probe_vkusvill, admitted survivors, and rewrote data/vless_pool.json + bin/xray/configs/active.json. But the running xray process (PID 3914525 on EC2, started 2026-05-05 15:27, systemd-managed) reads its config once at startup and never picks up rewrites.

So for about 4 days the pool JSON showed 16 healthy admitted RU nodes while the live xray kept routing every request to a dead outbound from May 5. leastPing balancer could not recover because observatory probes through the dead outbound also failed, and there was no fresh outbound in the running config to pivot to.

Fix applied manually this session: sudo systemctl restart saleapp-xray after whitelisting the 8 probed-good nodes in the pool. Bridge to vkusvill.ru went from HTTP 000 (15s timeout) to HTTP 200 (1.4 to 5s) immediately. Scheduler completed a full cycle with red 43, yellow 101, green 2, merged 146 within 2 minutes.

Evidence: commit b1d3b04 (UAT), bridge probe sequence in session 2026-05-10 19:00-19:20.

## Solution

TBD. Two approaches:

1. After refresh_proxy_list admits new nodes, call subprocess.run(["sudo", "systemctl", "restart", "saleapp-xray"]). Requires passwordless sudo for ubuntu on that unit. Restart is about 3s, bearable on refresh cadence. Only restart when the admitted set actually changed (compare old/new host sets) to avoid needless churn.

2. Drop systemd and let VlessProxyManager lazy-start its own xray (kill-and-restart cleanly inside the python process). Unifies lifecycle but means a backend crash kills the bridge for miniapp too.

Option 1 is less invasive. Also add a self-healing check: backend /admin/status compares pool.nodes[].host against xray.config.outbounds[].address and surfaces "xray stale" so monitoring catches this next time.

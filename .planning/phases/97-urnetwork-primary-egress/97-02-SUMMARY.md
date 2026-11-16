---
phase: 97
plan: 97-02
title: Route-aware preflight, UR-first candidates, bridge-first scheduling
status: complete
---

# 97-02 — Summary

Three layers, so a dead pool can never idle the scraper again.

**preflight** — `_probe_once(proxy, timeout, route)` extracted; `probe_bridge_alive()`
walks `_BRIDGE_PROXIES = (("urnetwork", 10809), ("vless", 10808))`, returns
`ProbeResult.route`, caches per route (`_LAST_SUCCESS_AT` became a dict), and
reports the primary route's failure when everything fails.

**candidates** — `proxy_candidates()` now returns URnetwork first, env/VLESS as
fallback (was the reverse). The fragile channel no longer burns the first timeout.

**scheduler** — `_prepare_proxy_connectivity()` order is now
direct -> answering bridge -> VLESS pool. Originally it required the UR route
specifically; the live probe showed UR dead and the balancer healthy
(`HTTP 200`, 3.8 s), so the code now accepts any answering bridge.

**observability** — `GET /api/admin/egress-probe` runs the same preflight inside
the backend and returns per-route `ok/status/reason/elapsed_s` plus the route that
would be handed to Chrome. This replaced "guess over SSH" (port 22 is DPI-blocked).

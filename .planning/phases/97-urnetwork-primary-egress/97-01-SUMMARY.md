---
phase: 97
plan: 97-01
title: Pinned URnetwork inbound + routing rule
status: complete
---

# 97-01 — Summary

`vless/config_gen.py`: new `XRAY_URN_LISTEN_PORT = 10809` and, when a UR
outbound exists, an `urn-socks-in` inbound with a pinned rule placed **first** in
`routing.rules`:

```python
{"type": "field", "inboundTag": ["urn-socks-in"], "outboundTag": "urn-ru-0"}
```

The general `socks-in` keeps `balancerTag`, so normal traffic still rotates over
the pool.

**Measured caveat (honest):** on the live box `urnetwork:10809` answers
`connect_error` because `data/urnetwork_proxy.json` is absent there — the
residential cache was never provisioned on this instance. The inbound therefore
is not created, which is the intended behaviour (it must not route into nothing).
The UR path will activate as soon as the cache exists; until then the balancer
bridge carries the traffic.

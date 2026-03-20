# Proxy Rotation for VkusVill IP Blocks

> Created: 2026-03-19 | Updated: 2026-03-19 21:49

## Problem

VkusVill periodically blocks the server IP (SSL handshake timeout, not explicit ban).
Blocks last 1.5–17 hours. On AWS the IP is static and can't be easily changed.

## Solution: SOCKS5 Proxy Auto-Rotation

Source: [proxifly/free-proxy-list](https://github.com/proxifly/free-proxy-list) — ~847 SOCKS5 proxies, **~43% success rate** for VkusVill HTTPS with valid SSL.

### Flow

```
Scheduler cycle starts
  │
  ├── check_direct() → can reach vkusvill.ru?
  │     │
  │     ├── YES → run scrapers normally (Chrome direct, no proxy)
  │     │
  │     └── NO → get_working_proxy()
  │               │
  │               ├── cached proxy alive? → use it instantly
  │               │
  │               └── no cache → refresh_proxy_list()
  │                     ├── fetch ~3400 proxies from proxifly
  │                     ├── normalize (strip socks5:// prefix)
  │                     ├── test with SSL verification + body check
  │                     ├── stop early at 10 good proxies (~1.5 min)
  │                     ├── cache top 10 fastest → data/working_proxies.json
  │                     └── restart Chrome with --proxy-server=socks5://ip:port
  │
  ├── run scrapers (RED → YELLOW → GREEN → MERGE)
  │     ├── real-time output parsing for kill triggers
  │     └── on failure: kill Chrome → pick new proxy → retry once
  │
  └── kill triggers: blocked(403), forbidden, vkusvill not available, err_proxy, err_connection
```

### Files

| File | Role |
|------|------|
| `proxy_manager.py` | Fetch, test (SSL+body), cache, rotate SOCKS5 proxies |
| `scheduler_service.py` | Proxy check before each cycle, kill triggers, retry logic |
| `chrome_stealth.py` | `restart_chrome_with_proxy()` — kill + relaunch Chrome with proxy |
| `timeout_activate.py` | Emergency kill script (scraper Chrome only, skips personal) |
| `data/working_proxies.json` | Cache of 10 working proxies (30 min TTL) |

### Key Constants

```python
SOCKS5_LIST_URLS = ["https://raw.githubusercontent.com/proxifly/.../all/data.txt"]
MAX_CACHED = 30          # Keep up to 30 proxies in pool
MIN_HEALTHY = 7          # Auto-refresh when pool drops below this
TEST_WORKERS = 30        # Concurrent threads (CPU-friendly)
PROBE_TIMEOUT = 8        # Per-proxy timeout
CACHE_TTL = 86400        # 24h daily refresh
SCRAPER_TIMEOUT = 120    # Hard timeout per scraper (seconds)
```

### Pool Chain (Self-Healing)

```
Every cycle:
  ensure_pool() → pool >= 7?
    ├── YES → use first proxy
    └── NO  → refresh_proxy_list(exclude=existing)
                ├── fetch ~3400 from proxifly
                ├── skip already-known proxies
                ├── test new ones, find up to (30 - current) 
                ├── merge with existing pool, sort by speed
                └── pool now has up to 30 proxies

On scraper failure:
  next_proxy() → remove dead proxy → pick next from pool
    └── if pool < 7 → ensure_pool() auto-triggers refresh

Daily: cache > 24h → full refresh regardless
```

### API

```python
pm.ensure_pool()         # auto-refresh if pool < 7 or stale
pm.pool_count()          # → int: current pool size
pm.pool_healthy()        # → bool: pool >= 7?
pm.remove_proxy(addr)    # drop dead proxy, saves cache
pm.next_proxy()          # remove current + return next (auto-refills)
pm.get_working_proxy()   # → "ip:port" (calls ensure_pool first)
pm.refresh_proxy_list(exclude=set)  # find new proxies, merge with existing
```

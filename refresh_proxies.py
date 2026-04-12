#!/usr/bin/env python3
"""One-shot proxy pool refresh."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from proxy_manager import ProxyManager

pm = ProxyManager()
pool = pm._cache.get("proxies", [])
print(f"Current pool: {len(pool)} proxies")
for p in pool:
    print(f"  {p['addr']}  speed={p.get('speed','?')}s  tested={p.get('tested_at','?')}")

print("\nRefreshing...")
n = pm.refresh_proxy_list()
print(f"\nFound {n} new proxies")

pool = pm._cache.get("proxies", [])
print(f"New pool: {len(pool)} proxies")
for p in sorted(pool, key=lambda x: x.get("speed", 999)):
    print(f"  {p['addr']}  speed={p.get('speed','?')}s  tested={p.get('tested_at','?')}")

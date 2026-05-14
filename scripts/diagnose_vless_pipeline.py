#!/usr/bin/env python3
"""Diagnose the VLESS refresh pipeline — where do candidate nodes die?

Usage: python3 scripts/diagnose_vless_pipeline.py

Reports:
  1. Total fetched + parse errors (now via fetch_all_sources)
  2. After RU filter (label OR unlabeled-fallthrough)
  3. Unique by (host, port)
  4. Cooldown / quarantine drops
  5. Per-source breakdown when --by-source is passed
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vless import sources, manager as manager_mod  # noqa: E402
from vless import quarantine as _quarantine  # noqa: E402


def main() -> int:
    by_source = "--by-source" in sys.argv

    print("[diagnose] fetching upstream lists (igareck + extras)...")
    if by_source:
        # Per-source breakdown.
        print("\n--- per-source counts ---")
        # igareck
        try:
            iga_text = sources.fetch_igareck_list()
            iga_nodes, iga_err = sources.parse_vless_list(iga_text)
            iga_ru, iga_rej = sources.filter_ru_nodes(iga_nodes)
            print(f"  igareck:    {len(iga_nodes):4d} parsed, {len(iga_ru):4d} RU/unlabeled, {len(iga_rej):4d} rejected")
        except Exception as e:
            print(f"  igareck failed: {e}")
        for url in sources.EXTRA_VLESS_SOURCES:
            try:
                body = sources._fetch_one(url, timeout=20.0)
                ns, errs = sources.parse_vless_list(body)
                ru, rej = sources.filter_ru_nodes(ns)
                tag = url.rsplit("/", 1)[-1]
                print(f"  {tag:30s}: {len(ns):4d} parsed, {len(ru):4d} RU/unlabeled, {len(rej):4d} rejected")
            except Exception as e:
                print(f"  {url} failed: {e}")
        print()

    text = sources.fetch_all_sources()
    parsed, parse_errors = sources.parse_vless_list(text)
    print(f"  parsed: {len(parsed)} nodes ({len(parse_errors)} parse errors)")

    ru_nodes, rejected = sources.filter_ru_nodes(parsed)
    print(f"  RU/unlabeled: {len(ru_nodes)} (rejected explicit non-RU: {len(rejected)})")

    # Unique by (host, port).
    by_host_port: Counter = Counter()
    for n in ru_nodes:
        by_host_port[(n.host, n.port)] += 1
    unique_hp = len(by_host_port)
    dup_hp = sum(c - 1 for c in by_host_port.values() if c > 1)
    print(f"  unique by host:port: {unique_hp} ({dup_hp} duplicates suppressed)")

    # Hostname vs IP literal.
    is_hostname = lambda h: not all(p.isdigit() and 0 <= int(p) <= 255 for p in h.split("."))  # noqa: E731
    hostnames = [h for h in {n.host for n in ru_nodes} if is_hostname(h)]
    print(f"  hostnames (need DNS lookup): {len(hostnames)}")

    # Build manager + replicate filter logic.
    pm = manager_mod.VlessProxyManager(register_atexit=False)
    pm._prune_expired_cooldowns()
    cooling = pm.cooldown_addrs()
    dead_hosts = {
        n["host"]
        for n in pm._pool.get("nodes", [])
        if n.get("host") and pm._is_node_dead(n)
    }
    quarantined = _quarantine.get_quarantined_hosts()
    print(f"  current pool size: {len(pm._pool.get('nodes', []))}")
    print(f"  cooldown hosts: {len(cooling)}")
    print(f"  dead hosts (REL-15): {len(dead_hosts)}")
    print(f"  quarantined host:port: {len(quarantined)}")

    candidates = []
    skip_cool = skip_dead = skip_quar = 0
    seen = set()
    for n in ru_nodes:
        if n.host in cooling:
            skip_cool += 1
            continue
        if n.host in dead_hosts:
            skip_dead += 1
            continue
        if f"{n.host}:{n.port}" in quarantined:
            skip_quar += 1
            continue
        key = (n.host, n.port)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(n)

    print()
    print("[diagnose] FUNNEL:")
    print(f"  upstream parsed:           {len(parsed):>4d}")
    print(f"  RU + unlabeled:            {len(ru_nodes):>4d}")
    print(f"  - cooldown:                {-skip_cool:>4d}")
    print(f"  - REL-15 dead:             {-skip_dead:>4d}")
    print(f"  - quarantined (probe-fail):{-skip_quar:>4d}")
    print(f"  candidates (deduped):      {len(candidates):>4d}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

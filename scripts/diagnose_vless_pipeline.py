#!/usr/bin/env python3
"""Diagnose the VLESS refresh pipeline — where do candidate nodes die?

Usage: python3 scripts/diagnose_vless_pipeline.py

Reports:
  1. Total fetched + parse errors
  2. After RU filter (by 🇷🇺 fragment label)
  3. Unique by (host, port)
  4. Unique by host only (collapse port variants)
  5. Cooldown-skipped count
  6. Quarantine-skipped count
  7. Already-in-pool count

This shows the operator EXACTLY how the 30+ entries in the upstream list
collapse to whatever ends up in the candidate set passed to
_probe_candidates_in_parallel.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vless import sources, manager as manager_mod  # noqa: E402
from vless import quarantine as _quarantine  # noqa: E402


def main() -> int:
    print("[diagnose] fetching upstream list...")
    text = sources.fetch_igareck_list()
    parsed, parse_errors = sources.parse_vless_list(text)
    print(f"  parsed: {len(parsed)} nodes ({len(parse_errors)} parse errors)")

    ru_nodes, rejected = sources.filter_ru_nodes(parsed)
    print(f"  RU-flagged: {len(ru_nodes)} (rejected non-RU: {len(rejected)})")

    # Unique by (host, port).
    by_host_port: Counter = Counter()
    for n in ru_nodes:
        by_host_port[(n.host, n.port)] += 1
    unique_hp = len(by_host_port)
    dup_hp = sum(c - 1 for c in by_host_port.values() if c > 1)
    print(f"  unique by host:port: {unique_hp} ({dup_hp} duplicates suppressed)")

    # Unique by host only.
    by_host: Counter = Counter()
    for n in ru_nodes:
        by_host[n.host] += 1
    unique_h = len(by_host)
    print(f"  unique by host only: {unique_h}")

    # Hostname vs IP literal.
    is_hostname = lambda h: not all(p.isdigit() and 0 <= int(p) <= 255 for p in h.split("."))  # noqa: E731
    hostnames = [h for h in by_host if is_hostname(h)]
    print(f"  hostnames (need DNS lookup): {len(hostnames)} -> {hostnames[:5]}{'...' if len(hostnames) > 5 else ''}")

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
    in_pool = {n["host"] for n in pm._pool.get("nodes", []) if n.get("host")}
    print(f"  current pool size: {len(pm._pool.get('nodes', []))}")
    print(f"  cooldown hosts: {len(cooling)} -> {sorted(cooling)[:5]}")
    print(f"  dead hosts (REL-15): {len(dead_hosts)}")
    print(f"  quarantined host:port: {len(quarantined)} -> {sorted(quarantined)[:8]}")

    candidates: list[tuple[str, int, str]] = []
    skip_cool = skip_dead = skip_quar = skip_in_pool = 0
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
        # NOTE: refresh_proxy_list also has an `exclude` set check, but this
        # is keyed on candidates the caller passes. By default empty.
        candidates.append((n.host, n.port, n.name[:40]))

    # Dedup by (host, port) — what the probe loop actually receives.
    seen = set()
    unique_candidates = []
    for c in candidates:
        key = (c[0], c[1])
        if key in seen:
            continue
        seen.add(key)
        unique_candidates.append(c)

    print()
    print("[diagnose] FUNNEL:")
    print(f"  upstream parsed:           {len(parsed):>4d}")
    print(f"  RU-flagged:                {len(ru_nodes):>4d}")
    print(f"  - cooldown:                {-skip_cool:>4d}")
    print(f"  - REL-15 dead:             {-skip_dead:>4d}")
    print(f"  - quarantined (probe-fail):{-skip_quar:>4d}")
    print(f"  candidates (with dups):    {len(candidates):>4d}")
    print(f"  candidates (deduped):      {len(unique_candidates):>4d}")
    print()
    print("[diagnose] dedup waste — same host:port appearing multiple times in candidates:")
    cand_hp_counter = Counter((c[0], c[1]) for c in candidates)
    dups = [(k, v) for k, v in cand_hp_counter.most_common() if v > 1]
    for (host, port), count in dups[:15]:
        print(f"  {count}x {host}:{port}")
    if len(dups) > 15:
        print(f"  ...and {len(dups) - 15} more duplicate keys")
    print(f"  total wasted probe slots: {sum(v - 1 for v in cand_hp_counter.values())}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

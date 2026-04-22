"""Audit current proxy pool for country distribution.

Reports: total count, how many are Russian (critical because VkusVill
restricted to RU IPs as of ~2026-04-17), top countries, and any
explicit Russian proxy addresses.

Usage (on EC2):
    python3 scripts/audit_proxy_countries.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from urllib.error import URLError

CACHE_FILE = os.environ.get(
    "PROXY_CACHE",
    "/home/ubuntu/saleapp/data/working_proxies.json",
)
BATCH_ENDPOINT = "http://ip-api.com/batch"
BATCH_SIZE = 100


def load_pool(path: str) -> list[str]:
    try:
        with open(path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
    except FileNotFoundError:
        print(f"ERROR: cache file {path} not found", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid JSON in {path}: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"updated_at={data.get('updated_at')}")
    entries = data.get("proxies", [])
    hosts: list[str] = []
    for entry in entries:
        addr = entry.get("addr") if isinstance(entry, dict) else entry
        if not addr:
            continue
        host = addr.split("://", 1)[-1].split(":", 1)[0]
        hosts.append(host)
    return hosts


def geo_lookup(ips: list[str]) -> list[dict]:
    results: list[dict] = []
    for start in range(0, len(ips), BATCH_SIZE):
        chunk = ips[start : start + BATCH_SIZE]
        body = json.dumps(
            [{"query": ip, "fields": "query,country,countryCode,isp"} for ip in chunk]
        ).encode()
        req = urllib.request.Request(
            BATCH_ENDPOINT,
            data=body,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                results.extend(json.loads(resp.read()))
        except URLError as exc:
            print(f"WARN: batch {start}: {exc}", file=sys.stderr)
    return results


def main() -> None:
    hosts = load_pool(CACHE_FILE)
    print(f"Total pooled proxies: {len(hosts)}")
    if not hosts:
        return

    geo = geo_lookup(hosts)
    by_cc: dict[str, int] = {}
    russians: list[dict] = []
    for row in geo:
        cc = row.get("countryCode") or "??"
        by_cc[cc] = by_cc.get(cc, 0) + 1
        if cc == "RU":
            russians.append(row)

    print(
        f"Russian IPs: {len(russians)}/{len(geo)} "
        f"({100 * len(russians) / max(len(geo), 1):.1f}%)"
    )
    print("Top countries:")
    for cc, n in sorted(by_cc.items(), key=lambda kv: -kv[1])[:15]:
        print(f"  {cc}: {n}")
    if russians:
        print("Russian proxies (usable):")
        for row in russians:
            print(f"  {row.get('query')}  ISP={row.get('isp')}")
    else:
        print("WARNING: zero Russian proxies in pool")


if __name__ == "__main__":
    main()

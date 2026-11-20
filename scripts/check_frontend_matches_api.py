#!/usr/bin/env python3
"""Compare what the public mini-app shows with what the API actually serves.

Why this exists: the operator catches discrepancies by screenshots, and a stale frontend
looks exactly like broken data ("Обновлено 6094 мин. назад" while /api/products was fresh).
A cached tab fooled me once on 20.11.2026 — the numbers were right in the API and stale in
my browser. This script makes that comparison mechanical, so "the site shows N" is never a
guess.

Exit codes: 0 — matches, 2 — mismatch or stale, 3 — unreachable.

Usage:
    python3 scripts/check_frontend_matches_api.py
    python3 scripts/check_frontend_matches_api.py --api http://152.70.58.201/api/products \
                                                  --front https://vkusvillsale.vercel.app/api/products
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone

DEFAULT_API = "http://152.70.58.201/api/products"
DEFAULT_FRONT = "https://vkusvillsale.vercel.app/api/products"
MAX_UPDATED_AGE_MIN = 45.0


def fetch(url: str, timeout: float = 30.0, proxy: str | None = None) -> dict:
    """Fetch JSON, optionally through a SOCKS/HTTP proxy.

    The Oracle host is not reachable directly from a Russian ISP (DPI), so the default
    local run needs the SOCKS endpoint the rest of this project uses. Shelling out to curl
    avoids a PySocks dependency and matches how every other probe here is run.
    """
    if proxy:
        import subprocess

        res = subprocess.run(
            ["curl", "-s", "--max-time", str(int(timeout)), "-x", proxy, url],
            capture_output=True, text=True,
        )
        if res.returncode != 0 or not res.stdout.strip():
            raise OSError(f"curl failed ({res.returncode}): {res.stderr.strip()[:120]}")
        return json.loads(res.stdout)
    req = urllib.request.Request(url, headers={"User-Agent": "saleapp-freshness-check"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — fixed hosts
        return json.loads(resp.read().decode("utf-8"))


def tier_counts(payload: dict) -> Counter:
    return Counter(p.get("type") for p in payload.get("products") or [])


# The API prints updatedAt in the server's local zone, which is Europe/Moscow (UTC+3).
# Parsing it as UTC made the age come out as -178 min — a "future" timestamp that would
# have been reported as a bug in the frontend rather than in my parser.
SERVER_TZ = timezone(timedelta(hours=3))


def parse_updated(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value[:19], fmt).replace(tzinfo=SERVER_TZ)
        except ValueError:
            continue
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default=DEFAULT_API)
    ap.add_argument("--front", default=DEFAULT_FRONT)
    ap.add_argument("--proxy", default=None,
                    help="e.g. socks5h://127.0.0.1:10870 — needed locally, the host is DPI-blocked")
    args = ap.parse_args()

    try:
        api = fetch(args.api, proxy=args.proxy)
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        print(f"❌ API unreachable: {type(exc).__name__}: {exc}")
        return 3

    api_counts = tier_counts(api)
    api_updated = parse_updated(api.get("updatedAt"))
    print(f"API   : total={sum(api_counts.values())} green={api_counts['green']} "
          f"red={api_counts['red']} yellow={api_counts['yellow']} "
          f"updatedAt={api.get('updatedAt')} stale={api.get('dataStale')}")

    try:
        front = fetch(args.front, proxy=args.proxy)
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        print(f"❌ Frontend API unreachable: {type(exc).__name__}: {exc}")
        return 3

    front_counts = tier_counts(front)
    front_updated = parse_updated(front.get("updatedAt"))
    print(f"FRONT : total={sum(front_counts.values())} green={front_counts['green']} "
          f"red={front_counts['red']} yellow={front_counts['yellow']} "
          f"updatedAt={front.get('updatedAt')} stale={front.get('dataStale')}")

    problems: list[str] = []
    for tier in ("green", "red", "yellow"):
        if abs(api_counts[tier] - front_counts[tier]) > 0:
            problems.append(f"{tier}: API {api_counts[tier]} != FRONT {front_counts[tier]}")

    if front_updated is None:
        problems.append("frontend has no usable updatedAt")
    else:
        age_min = (datetime.now(timezone.utc) - front_updated).total_seconds() / 60
        print(f"FRONT updatedAt age: {age_min:.1f} min (limit {MAX_UPDATED_AGE_MIN:.0f})")
        if age_min > MAX_UPDATED_AGE_MIN:
            problems.append(f"frontend data is {age_min:.0f} min old")
        if api_updated and (api_updated - front_updated).total_seconds() > 600:
            problems.append("frontend is behind the API by more than 10 min")

    if problems:
        print("❌ Mismatch:")
        for p in problems:
            print(f"   - {p}")
        return 2

    print("✅ Frontend matches the API across all three tiers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
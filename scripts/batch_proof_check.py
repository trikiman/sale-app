#!/usr/bin/env python3
"""Collect the Phase-96 multi-batch evidence from the admin log endpoint.

Why this file exists: `~/.hermes/scripts/saleapp_batch_proof.sh` asks the API for
`/api/admin/logs`, which the backend does not serve — the real route is `/admin/logs`
(`backend/main.py:6213`). Every run therefore got a 404, hit the `[ ! -s "$TMP" ] && exit 0`
guard, and exited silently: the collector has recorded nothing since it was installed,
and the one morning window that can still produce the proof would have been lost the
same way.

This script talks to the correct route, prints what it found, and exits with a code the
caller can gate on:
    0  >= 2 distinct `Batch a-b` ranges in one log window  -> multi-batch proof
    3  fewer ranges found                                  -> keep waiting
    2  endpoint unreachable / unexpected payload           -> unknown, not proof

Read-only: one GET. No cart actions, no scraper runs.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_API = "http://152.70.58.201"
DEFAULT_PROXY = "socks5h://127.0.0.1:10870"
PROJ = Path(__file__).resolve().parent.parent

BATCH_RE = re.compile(r"Batch (\d+-\d+)")
HIT_RE = re.compile(
    r"(Batch \d+-\d+|items to cart|Green cards rendered|Inline add-to-cart|stopping the loader)"
)


def read_token(proj: Path = PROJ) -> str:
    env = proj / ".env"
    for line in env.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("ADMIN_TOKEN="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("batch-proof: ADMIN_TOKEN not found in " + str(env))


def fetch_lines(api: str, token: str, n: int, proxy: str | None) -> list[str]:
    cmd = ["curl", "-s", "--max-time", "45", "-H", f"X-Admin-Token: {token}",
           f"{api}/admin/logs?n={n}"]
    if proxy:
        cmd[1:1] = ["-x", proxy]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"curl exit {proc.returncode}: {proc.stderr.strip()[:200]}")
    body = (proc.stdout or "").strip()
    if not body:
        raise RuntimeError("empty response")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise RuntimeError(f"non-JSON response: {body[:120]}")
    if not isinstance(payload, dict) or "lines" not in payload:
        raise RuntimeError(f"unexpected payload keys: {list(payload)[:5] if isinstance(payload, dict) else type(payload).__name__}")
    return [x if isinstance(x, str) else json.dumps(x, ensure_ascii=False) for x in (payload["lines"] or [])]


def summarize(lines: list[str]) -> dict:
    hits = [x for x in lines if HIT_RE.search(x)]
    ranges = sorted({m for x in hits for m in BATCH_RE.findall(x)})
    added = [x.strip() for x in hits if "items to cart" in x]
    return {
        "lines": len(lines),
        "hits": len(hits),
        "ranges": ranges,
        "distinct_ranges": len(ranges),
        "added_lines": added[-3:],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Phase-96 multi-batch proof collector")
    ap.add_argument("--api", default=os.environ.get("SALEAPP_API", DEFAULT_API))
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--proxy", default=DEFAULT_PROXY)
    ap.add_argument("--no-proxy", action="store_true")
    ap.add_argument("--need", type=int, default=2, help="distinct ranges that count as proof")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    try:
        lines = fetch_lines(args.api, read_token(), args.n, None if args.no_proxy else args.proxy)
    except (RuntimeError, OSError) as exc:
        print(f"batch-proof: {exc}", file=sys.stderr)
        return 2

    s = summarize(lines)
    if args.json:
        print(json.dumps(s, ensure_ascii=False))
    else:
        print(f"lines={s['lines']} hits={s['hits']} distinct_batch_ranges={s['distinct_ranges']} "
              f"ranges={','.join(s['ranges']) or '-'}")
        for x in s["added_lines"]:
            print("  " + x)

    if s["distinct_ranges"] >= args.need:
        print(f"BATCH PROOF: multi-batch observed — {s['distinct_ranges']} distinct ranges in one window")
        return 0
    print(f"batch-proof: {s['distinct_ranges']} distinct range(s), need {args.need} — keep waiting")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
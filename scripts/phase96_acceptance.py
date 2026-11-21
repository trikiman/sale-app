#!/usr/bin/env python3
"""Phase 96 acceptance runner — run on/after 2026-11-26 09:18 MSK.

The soak report's checklist has six steps; this script performs the four that can be
checked mechanically and prints the two that stay human (closing the phase, then the
milestone audit). It NEVER closes anything: acceptance is a decision, not a side
effect, so the last word stays with the operator.

Checks, in order:
  1. the report is reachable and its numbers are read;
  2. `false_zero_cycles == 0`;
  3. `gap_incident_count == 0` (the 168 h window holds no gap at all);
  4. `hours_recorded >= 168`;
  5. no gap newer than ACCEPTANCE_EPOCH — belt and braces on top of (3).

Exit codes: 0 = all checks passed, 2 = at least one failed, 3 = endpoint unreachable.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(PROJECT, ".env")
API = "http://152.70.58.201/api/admin/green-uptime?hours=168&tail=200"
PROXY = "socks5h://127.0.0.1:10870"
# First moment the 168 h window holds no gap AND no false zero: the last incident is
# the false zero at 2026-11-20 05:12:12 UTC, so the window clears 168 h later.
ACCEPTANCE_EPOCH = dt.datetime(2026, 11, 28, 6, 0, tzinfo=dt.timezone.utc).timestamp()
REQUIRED_HOURS = 168


def _token() -> str | None:
    try:
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("ADMIN_TOKEN="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        return None
    return None


def fetch(token: str) -> dict | None:
    try:
        out = subprocess.run(
            ["curl", "-s", "--max-time", "60", "-x", PROXY,
             "-H", f"X-Admin-Token: {token}", API],
            capture_output=True, text=True, timeout=90,
        )
        return json.loads(out.stdout)
    except Exception:
        return None


def evaluate(report: dict) -> list[tuple[str, bool, str]]:
    """Return [(check name, passed, detail)] — pure, so it can be unit-tested."""
    zeros = report.get("false_zero_cycles", 0) or 0
    gaps = report.get("gap_incident_count", 0) or 0
    hours = report.get("hours_recorded", 0) or 0
    incidents = report.get("gap_incidents") or []
    post = [g for g in incidents if (g.get("from_ts") or 0) > ACCEPTANCE_EPOCH]

    return [
        ("false_zero_cycles == 0", zeros == 0, f"{zeros}"),
        ("gap_incident_count == 0", gaps == 0, f"{gaps}"),
        (f"hours_recorded >= {REQUIRED_HOURS}", hours >= REQUIRED_HOURS, f"{hours}"),
        ("no gap after acceptance epoch", not post, f"{len(post)} post-epoch gap(s)"),
    ]


def main() -> int:
    token = _token()
    if not token:
        print("no ADMIN_TOKEN in .env")
        return 3
    report = fetch(token)
    if not report or "verdict" not in report:
        print("⚠️ report endpoint unreachable — acceptance cannot be judged")
        return 3

    print(f"verdict: {report.get('verdict')}")
    print(
        f"cycles: {report.get('cycles')} "
        f"({report.get('cycles_ok')} ok / {report.get('cycles_failed')} failed), "
        f"uptime: {report.get('uptime_pct')}%"
    )
    results = evaluate(report)
    for name, ok, detail in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name} — {detail}")

    if not all(ok for _n, ok, _d in results):
        print("\n❌ Acceptance NOT met. Do not close phase 96.")
        return 2

    print("\n✅ All mechanical checks passed. Remaining, human-owned steps:")
    print("   gsd-tools state complete-phase --phase 96")
    print("   then gsd-audit-milestone / gsd-complete-milestone for v1.30")
    return 0


if __name__ == "__main__":
    sys.exit(main())

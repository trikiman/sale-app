#!/usr/bin/env python3
"""v1.30 Phase 96 — daily green soak check.

Asks the live server for the 168-hour green uptime report and appends one line
to the soak log in `.planning/phases/96-soak-and-uptime-report/96-SOAK.md`.

Exit codes (so cron can tell the difference):
  0  healthy / insufficient-but-running soak
  2  incident — a gap over 45 min or a false green zero inside the window
  3  the report endpoint could not be reached (server down / tunnel down)

The admin token is read from the project `.env` (`ADMIN_TOKEN`); it is never
printed, echoed, or written into the log.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(PROJECT, ".env")
SOAK_LOG = os.path.join(
    PROJECT, ".planning", "phases", "96-soak-and-uptime-report", "96-SOAK.md"
)
API = "http://152.70.58.201/api/admin/green-uptime?hours=168"
PROXY = "socks5h://127.0.0.1:10870"


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
    """Call the endpoint through the local SOCKS tunnel (server 22 is blocked)."""
    try:
        out = subprocess.run(
            [
                "curl", "-s", "--max-time", "40", "-x", PROXY,
                "-H", f"X-Admin-Token: {token}", API,
            ],
            capture_output=True, text=True, timeout=60,
        )
        return json.loads(out.stdout)
    except Exception:
        return None


def main() -> int:
    token = _token()
    if not token:
        print("no ADMIN_TOKEN in .env")
        return 3

    report = fetch(token)
    if not report:
        line = (
            f"- **{dt.date.today().isoformat()}** — ⚠️ endpoint unreachable "
            f"(server or tunnel down); soak status unknown.\n"
        )
        _append(line)
        print(line.strip())
        return 3

    verdict = report.get("verdict")
    gaps = report.get("gap_incident_count", 0)
    zeros = report.get("false_zero_count", 0)
    cycles = report.get("cycles", 0)
    uptime = report.get("uptime_pct")
    age = report.get("last_ok_age_minutes")

    icon = {"healthy": "✅", "incident": "🔴", "insufficient": "⏳", "no_data": "⏳"}.get(str(verdict), "❓")
    line = (
        f"- **{dt.date.today().isoformat()}** — {icon} verdict `{verdict}`, "
        f"cycles {cycles} (uptime {uptime}%), gaps {gaps}, false zeros {zeros}, "
        f"last ok {age} min ago.\n"
    )
    _append(line)
    print(line.strip())

    return 2 if verdict == "incident" else 0


def _append(line: str) -> None:
    try:
        with open(SOAK_LOG, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass


if __name__ == "__main__":
    sys.exit(main())
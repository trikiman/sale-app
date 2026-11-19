#!/usr/bin/env python3
"""v1.30 Phase 96 — daily green soak check.

Asks the live server for the 168-hour green uptime report and appends one line
to the soak log in `.planning/phases/96-soak-and-uptime-report/96-SOAK.md`.

Exit codes (so cron can tell the difference):
  0  healthy / insufficient-but-running soak
  2  incident — a gap over 45 min or a false green zero inside the window
  3  the report endpoint could not be reached (server down / tunnel down)
  4  incident, but ONLY because historical pre-fix gaps have not aged out of the
     168 h window yet (no gap newer than FIX_MARK). Not an alarm: acceptance reads
     2026-11-25 after the last such gap leaves the window. A gap newer than
     FIX_MARK is a real event and still returns 2.

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
    new_gaps = _new_gaps(report)
    zeros = report.get("false_zero_count", 0)
    cycles = report.get("cycles", 0)
    uptime = report.get("uptime_pct")
    age = report.get("last_ok_age_minutes")

    historic = 0 if new_gaps is None else max(0, gaps - new_gaps)
    icon = {"healthy": "✅", "incident": "🔴", "insufficient": "⏳", "no_data": "⏳"}.get(str(verdict), "❓")
    note = ""
    if new_gaps:
        note = f" ⚠️ NEW gaps after fix: {new_gaps}"
    elif historic:
        note = f" ⏳ window still holds {historic} pre-fix gap(s); acceptance 2026-11-25"
    line = (
        f"- **{dt.date.today().isoformat()}** — {icon} verdict `{verdict}`, "
        f"cycles {cycles} (uptime {uptime}%), gaps {gaps}, false zeros {zeros}, "
        f"last ok {age} min ago.{note}\n"
    )
    _append(line)
    print(line.strip())

    if verdict != "incident":
        return 0
    if new_gaps:
        return 2          # a real, post-fix gap — alarm
    return 4              # only pre-fix gaps remain in the window


# End of the last pre-fix gap (18.11 05:12 -> 06:21 UTC). Anything at or before this
# is history that the 168 h window will drop by 2026-11-25 06:21 UTC.
FIX_MARK_TS = 1794982887.0


def _new_gaps(report: dict) -> int | None:
    """Gaps that started AFTER the fix — the only ones that mean the fix failed."""
    incidents = report.get("gap_incidents")
    if not isinstance(incidents, list):
        return None
    # Keyed on the gap's START: the pre-fix gap begins 18.11 05:12, well before the
    # mark, while any gap caused by a post-fix regression starts after it.
    return sum(1 for g in incidents if (g.get("from_ts") or 0) > FIX_MARK_TS)


def _append(line: str) -> None:
    try:
        with open(SOAK_LOG, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass


if __name__ == "__main__":
    sys.exit(main())
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
    zeros = report.get("false_zero_cycles", 0) or 0
    new_gaps = _new_gaps(report)
    new_zeros = max(0, zeros - len(KNOWN_FALSE_ZEROS))
    cycles = report.get("cycles", 0)
    uptime = report.get("uptime_pct")
    age = report.get("last_ok_age_minutes")

    historic = 0 if new_gaps is None else max(0, gaps - new_gaps)
    icon = {"healthy": "✅", "incident": "🔴", "insufficient": "⏳", "no_data": "⏳"}.get(str(verdict), "❓")
    note = ""
    if new_zeros:
        note = f" 🚨 FALSE ZEROS beyond the diagnosed one: {new_zeros}"
    elif new_gaps:
        note = f" ⚠️ UNDIAGNOSED new gaps: {new_gaps}"
    elif zeros:
        note = f" ⏳ {zeros} diagnosed false zero(s) in window; acceptance {ACCEPTANCE_UTC}"
    elif historic:
        note = (
            f" ⏳ window still holds {historic} known gap(s) (pre-fix + diagnosed "
            f"post-fix); acceptance {ACCEPTANCE_UTC}"
        )
    line = (
        f"- **{dt.date.today().isoformat()}** — {icon} verdict `{verdict}`, "
        f"cycles {cycles} (uptime {uptime}%), gaps {gaps}, false zeros {zeros}, "
        f"last ok {age} min ago.{note}\n"
    )
    _append(line)
    print(line.strip())

    if verdict != "incident":
        return 0
    if new_zeros:
        return 2          # an undiagnosed false zero — the milestone's core failure
    if new_gaps:
        return 2          # a real, post-fix gap — alarm
    return 4              # only known gaps / diagnosed false zeros remain


# End of the last pre-fix gap (18.11 05:12 -> 06:21 UTC). Gaps ending at or before
# this are history that the 168 h window drops on 2026-11-25 06:21 UTC.
FIX_MARK_TS = 1794982887.0

# Gaps already investigated and written up in 96-SOAK.md, with the reason they are
# NOT an open regression: (from_ts, to_ts, why). Matching one of these keeps the check
# at exit 4 ("still waiting") instead of crying alarm forever; anything else is exit 2.
# Never add an entry here without a written diagnosis in the soak log — otherwise this
# list silently becomes a way to mute real alarms.
KNOWN_GAPS = [
    (1795064070.669, 1795069112.662,
     "gap #8, 19.11 04:54-06:18 UTC: egress stall on the only live route "
     "(urnetwork), every navigation hit its deadline; recovered on its own"),
    (1795185191.048, 1795188044.052,
     "gap #9, 20.11 17:33-18:20 MSK (14:33-15:20 UTC): self-inflicted — a run of "
     "consecutive deploys for the RED/YELLOW card-render fix restarted the scheduler "
     "several times in a row, so no GREEN cycle could finish inside the window. "
     "Diagnosed, expected, and NOT a scraper fault; the very next cycle after the "
     "last restart completed normally (Found 18 green products)."),
]
KNOWN_GAP_TOLERANCE_S = 120

# First moment the 168 h window holds no gap at all (end of the latest diagnosed gap
# + 168 h). Printed in the log line so the daily note never says an outdated date.
ACCEPTANCE_UTC = "2026-11-27 05:12 UTC (08:12 MSK)"

# False zeros are cycles that reported exit 0 with live_count 0 and no VkusVill
# "nothing is marked down" reason — the exact thing v1.30 exists to kill. Each one is
# diagnosed and listed here with its ts; anything beyond this count is a live alarm.
KNOWN_FALSE_ZEROS = [
    (1795151532.0,
     "20.11 05:12:12 UTC: exited 0 with live_count 0 and empty_reason=unknown_empty "
     "(empty page, no VkusVill banner). Night-time green was already empty; the run "
     "could not prove why, yet still claimed success."),
]


def _is_known(gap: dict) -> bool:
    start = gap.get("from_ts") or 0
    end = gap.get("to_ts") or 0
    return any(
        abs(start - k_start) <= KNOWN_GAP_TOLERANCE_S
        and abs(end - k_end) <= KNOWN_GAP_TOLERANCE_S
        for k_start, k_end, _why in KNOWN_GAPS
    )


def _new_gaps(report: dict) -> int | None:
    """Gaps after the fix mark that are NOT already diagnosed — the real alarms."""
    incidents = report.get("gap_incidents")
    if not isinstance(incidents, list):
        return None
    # Keyed on the gap's START: pre-fix gaps begin before the mark, a regression after.
    return sum(
        1 for g in incidents
        if (g.get("from_ts") or 0) > FIX_MARK_TS and not _is_known(g)
    )


def _append(line: str) -> None:
    try:
        with open(SOAK_LOG, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass


if __name__ == "__main__":
    sys.exit(main())
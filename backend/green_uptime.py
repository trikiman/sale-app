"""Green uptime recorder (v1.30 GREEN-UP-03 / Phase 96).

The milestone goal — "зелёные ценники не отлетают целую неделю" — is only
provable with a per-cycle record, not with a spot check at the moment someone
asks. This module appends one JSONL line per green cycle and computes the
7-day (168 h) summary.

Dependency-free by design (no FastAPI, no threading) so it is fully testable
in the plain venv.

File format: one JSON object per line:

    {"ts": 1763000000.0, "ok": true, "exit_code": 0,
     "live_count": 12, "empty_reason": null, "duration_s": 143.2}

Incident definitions (deliberately narrow — only real failures count):

- **gap incident**: more than GAP_INCIDENT_MINUTES between two successful
  cycles (or since the last successful cycle and now). A gap means the UI was
  serving a stale snapshot past its threshold.
- **false zero**: a cycle that exited 0 while reporting `live_count == 0`
  without VkusVill's own `source_empty`/`missing` reason — i.e. we claimed
  success and still had nothing to show.
- A cycle that ended with `source_empty` is a legitimate empty store, not an
  incident: the point of v1.30 is that *false* zeros die, not that green offers
  never legitimately run out.
"""

from __future__ import annotations

import json
import os
import time

DEFAULT_WINDOW_HOURS = 168  # the milestone goal: one week
GAP_INCIDENT_MINUTES = 45   # == the green staleness threshold
LEGITIMATE_EMPTY_REASONS = ("source_empty", "missing")
_ROTATE_BYTES = 2_000_000   # ~2 MB ≈ months of one-line records

REQUIRED_FIELDS = ("ts", "ok", "exit_code", "live_count", "empty_reason", "duration_s")


def record_cycle(
    path: str,
    *,
    ts: float,
    ok: bool,
    exit_code: int | None,
    live_count: int | None,
    empty_reason: str | None,
    duration_s: float | None,
) -> None:
    """Append one cycle record; rotate the file when it grows past the cap.

    Never raises: a broken recorder must not take the scrape down with it.
    """
    try:
        entry = {
            "ts": round(float(ts), 3),
            "ok": bool(ok),
            "exit_code": exit_code,
            "live_count": live_count,
            "empty_reason": empty_reason,
            "duration_s": round(float(duration_s), 1) if duration_s is not None else None,
        }
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        if os.path.exists(path) and os.path.getsize(path) > _ROTATE_BYTES:
            os.replace(path, path + ".1")  # keep one previous generation
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _load(path: str) -> list[dict]:
    entries: list[dict] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue  # a torn line never invalidates the whole log
                if isinstance(obj, dict) and all(k in obj for k in REQUIRED_FIELDS):
                    entries.append(obj)
    except OSError:
        pass
    entries.sort(key=lambda e: e["ts"])
    return entries


def recent(path: str, limit: int = 20) -> list[dict]:
    """Last ``limit`` cycle records, newest last.

    Diagnostic companion to :func:`summarize`: the aggregates say *how often* a
    cycle failed, this says *which* ones and with what duration, which is what
    you need before guessing at a cause.
    """
    entries = _load(path)
    return entries[-max(1, int(limit)):]


def summarize(path: str, *, now: float | None = None, window_hours: float = DEFAULT_WINDOW_HOURS) -> dict:
    """Compute the uptime report over the trailing window.

    ``verdict`` is one of:

    - ``no_data``   — the record does not exist / is empty;
    - ``insufficient`` — less than 24 h or fewer than 10 cycles in the window:
      honest answer is "cannot judge yet", not "healthy";
    - ``healthy``   — zero gap incidents and zero false zeros in the window;
    - ``incident``  — at least one of either.
    """
    now = time.time() if now is None else now
    window_start = now - window_hours * 3600
    entries = [e for e in _load(path) if e["ts"] >= window_start]

    if not entries:
        return {
            "verdict": "no_data",
            "window_hours": window_hours,
            "cycles": 0,
        }

    ok_entries = [e for e in entries if e["ok"]]
    cycles_ok = len(ok_entries)

    # Gap incidents: dead air between successes (or trailing dead air to now).
    gaps = []
    prev_ts = None
    for e in ok_entries:
        if prev_ts is not None:
            gap_min = (e["ts"] - prev_ts) / 60
            if gap_min > GAP_INCIDENT_MINUTES:
                gaps.append(
                    {
                        "from_ts": prev_ts,
                        "to_ts": e["ts"],
                        "minutes": round(gap_min, 1),
                    }
                )
        prev_ts = e["ts"]

    trailing_min = None
    if ok_entries:
        trailing_min = round((now - ok_entries[-1]["ts"]) / 60, 1)
        if trailing_min > GAP_INCIDENT_MINUTES:
            gaps.append({"from_ts": ok_entries[-1]["ts"], "to_ts": None, "minutes": trailing_min})

    # False zeros: claimed success, no products, no legitimate reason.
    false_zeros = [
        {
            "ts": e["ts"],
            "empty_reason": e["empty_reason"],
        }
        for e in ok_entries
        if (e["live_count"] or 0) == 0
        and e["empty_reason"] not in LEGITIMATE_EMPTY_REASONS
    ]

    # Legitimate empty cycles (VkusVill itself reported no green offers).
    legit_empty = sum(
        1 for e in ok_entries if e["empty_reason"] in LEGITIMATE_EMPTY_REASONS
    )

    hours_covered = (entries[-1]["ts"] - entries[0]["ts"]) / 3600 if len(entries) > 1 else 0
    uptime_pct = round(100 * cycles_ok / len(entries), 2) if entries else 0

    if hours_covered < 24 or len(entries) < 10:
        verdict = "insufficient"
    elif gaps or false_zeros:
        verdict = "incident"
    else:
        verdict = "healthy"

    worst_gap = max((g["minutes"] for g in gaps), default=None)
    return {
        "verdict": verdict,
        "window_hours": window_hours,
        "window_start": window_start,
        "cycles": len(entries),
        "cycles_ok": cycles_ok,
        "cycles_failed": len(entries) - cycles_ok,
        "uptime_pct": uptime_pct,
        "last_ok_age_minutes": trailing_min,
        "worst_gap_minutes": worst_gap,
        "gap_incidents": gaps,
        "gap_incident_count": len(gaps),
        "false_zero_cycles": len(false_zeros),
        "false_zero_count": len(false_zeros),
        "legit_empty_cycles": legit_empty,
        "hours_recorded": round(hours_covered, 1),
    }
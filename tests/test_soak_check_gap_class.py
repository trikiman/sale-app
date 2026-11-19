"""The daily soak check must not cry wolf over gaps that are already history.

`verdict: incident` stays true until the 168 h window drops the last pre-fix gap
(2026-11-25 06:21 UTC). A cron that exits 2 every day for that reason trains the
operator to ignore it, and the real alarm — a gap caused by a post-fix regression —
gets lost. So the check now separates the two:

- any gap that STARTED after the fix mark (18.11 06:21 UTC) -> exit 2, real alarm;
- only pre-fix gaps left in the window -> exit 4, "still waiting".

Keyed on from_ts, not to_ts: the pre-fix gap started 18.11 05:12 and a regression
gap would start later, which keeps the boundary unambiguous.
"""
from __future__ import annotations

import importlib.util
import pathlib

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "green_soak_check.py"


def _mod():
    spec = importlib.util.spec_from_file_location("green_soak_check", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _gap(start, end=0.0):
    return {"from_ts": start, "to_ts": end, "minutes": 60}


def test_pre_fix_gap_is_not_counted_as_new() -> None:
    mod = _mod()
    report = {"gap_incidents": [_gap(mod.FIX_MARK_TS - 3600, mod.FIX_MARK_TS - 1800)]}
    assert mod._new_gaps(report) == 0


def test_post_fix_gap_is_counted() -> None:
    mod = _mod()
    report = {"gap_incidents": [_gap(mod.FIX_MARK_TS + 60, mod.FIX_MARK_TS + 120)]}
    assert mod._new_gaps(report) == 1


def test_missing_incident_list_is_unknown_not_zero() -> None:
    mod = _mod()
    assert mod._new_gaps({}) is None


def test_exit_codes_documented() -> None:
    src = SCRIPT.read_text(encoding="utf-8")
    assert "  4  incident, but ONLY because historical" in src
    assert "return 4" in src

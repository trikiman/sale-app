"""Acceptance logic for phase 96 must be strict and side-effect free.

The 168-hour soak is the whole milestone, so the check that decides "passed" has to be
testable without waiting a week. `evaluate()` is pure: feed it report dicts and read
the verdicts. It must fail on any false zero, any gap in the window, too few recorded
hours, and any gap that started after the acceptance epoch.
"""
from __future__ import annotations

import importlib.util
import pathlib

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "phase96_acceptance.py"


def _mod():
    spec = importlib.util.spec_from_file_location("phase96_acceptance", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _report(**over):
    base = {
        "verdict": "healthy",
        "false_zero_cycles": 0,
        "gap_incident_count": 0,
        "hours_recorded": 168.4,
        "gap_incidents": [],
    }
    base.update(over)
    return base


def _passed(results):
    return {name: ok for name, ok, _detail in results}


def test_clean_window_passes() -> None:
    mod = _mod()
    assert all(ok for _n, ok, _d in mod.evaluate(_report()))


def test_false_zero_fails() -> None:
    mod = _mod()
    res = _passed(mod.evaluate(_report(false_zero_cycles=1)))
    assert res["false_zero_cycles == 0"] is False


def test_any_gap_fails_even_if_old() -> None:
    mod = _mod()
    res = _passed(mod.evaluate(_report(gap_incident_count=1)))
    assert res["gap_incident_count == 0"] is False


def test_healthy_span_passes_at_the_real_ceiling() -> None:
    """A healthy week records ~167.8 h, not 168 — the span excludes the two partial cycles.

    Pinned because `hours_recorded >= 168` looked strict but was unsatisfiable: the last
    record is always minutes old, so the check judged the clock, not the soak.
    """
    mod = _mod()
    assert mod.MIN_HOURS == mod.REQUIRED_HOURS - mod.PARTIAL_CYCLE_TOLERANCE_H
    res = _passed(mod.evaluate(_report(hours_recorded=167.9)))
    assert res[f"hours_recorded >= {mod.MIN_HOURS} ({mod.REQUIRED_HOURS} h minus 45 min partial cycles)"] is True


def test_short_recording_fails() -> None:
    mod = _mod()
    res = _passed(mod.evaluate(_report(hours_recorded=166.9)))
    assert res[f"hours_recorded >= {mod.MIN_HOURS} ({mod.REQUIRED_HOURS} h minus 45 min partial cycles)"] is False


def test_post_epoch_gap_fails() -> None:
    mod = _mod()
    report = _report(gap_incidents=[{"from_ts": mod.ACCEPTANCE_EPOCH + 10, "to_ts": mod.ACCEPTANCE_EPOCH + 4000}])
    res = _passed(mod.evaluate(report))
    assert res["no gap after acceptance epoch"] is False


def test_acceptance_epoch_is_the_documented_moment() -> None:
    """The epoch must sit AFTER the last gap has left the 168 h window.

    The window arithmetic, not the calendar, decides this. Gap #10 ended 20.11 23:35 MSK
    (leaves 27.11 23:35 MSK); gap #11 ended 21.11 08:47 MSK and therefore leaves only at
    28.11 08:47 MSK, which makes 28.11 00:00 MSK arithmetic that cannot pass. Every previous
    epoch (25.11, 26.11 09:18, 27.11 08:12, 28.11 00:00) was invalidated by a new gap, not by
    a real defect in the acceptance criteria.
    """
    mod = _mod()
    when = __import__("datetime").datetime.fromtimestamp(mod.ACCEPTANCE_EPOCH, __import__("datetime").timezone.utc)
    assert when.strftime("%Y-%m-%d %H:%M") == "2026-11-28 06:00"

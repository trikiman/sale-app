"""v1.30 Phase 95 (GREEN-UP-02) — a stuck run must not hold the lock forever.

Measured failure (2026-11-15): `green_products.json` went 42 minutes untouched
while the scheduler kept logging "Already running, skipping". The worker thread
was blocked reading stdout of a live-but-silent child, so its `finally` never
cleared `scraper_status["green"]["running"]`.

The decision lives in `backend/run_guard.py` (no FastAPI/telegram imports) so it
is testable in the plain venv.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "backend"))


def _zombie(started_at, now, stale_seconds=900):
    from run_guard import is_zombie_run

    return is_zombie_run(started_at, now, stale_seconds)


def test_fresh_run_is_not_a_zombie() -> None:
    assert _zombie(started_at=1_000.0, now=1_060.0) is False


def test_run_exactly_at_limit_is_not_yet_a_zombie() -> None:
    assert _zombie(started_at=1_000.0, now=1_900.0, stale_seconds=900) is False


def test_run_past_limit_is_a_zombie() -> None:
    assert _zombie(started_at=1_000.0, now=1_901.0, stale_seconds=900) is True


def test_missing_timestamp_is_treated_as_zombie() -> None:
    """A flag set without a timestamp must not block the first tick after upgrade."""
    assert _zombie(started_at=None, now=5_000.0) is True


def test_zero_timestamp_is_treated_as_zombie() -> None:
    assert _zombie(started_at=0.0, now=5_000.0) is True


@pytest.mark.parametrize("elapsed,expected", [(0, False), (299, False), (900, False), (901, True), (3600, True)])
def test_bounds_match_the_scheduler_ceiling(elapsed: int, expected: bool) -> None:
    """A green cycle is capped at 300 s; 900 s means dead, not slow."""
    assert _zombie(started_at=10_000.0, now=10_000.0 + elapsed) is expected


def test_default_threshold_triples_the_scraper_timeout() -> None:
    from run_guard import DEFAULT_STALE_SECONDS

    assert DEFAULT_STALE_SECONDS == 900, "must stay 3x the 300 s scraper ceiling"


# ── wiring: the endpoint must actually consult the guard ────────────────


def test_main_consults_the_zombie_guard_before_skipping() -> None:
    source = (_REPO_ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    assert "is_zombie_run(" in source
    # Match the actual log call, not the explanatory comment above the guard.
    skip_idx = source.find('log_buffer.append(f"[{name}] Already running, skipping.")')
    assert skip_idx != -1
    guard_idx = source.find("_run_flag_is_zombie(name)")
    assert guard_idx != -1, "the zombie check disappeared from _run_script"
    # The guard must be evaluated shortly before the skip decision, i.e. the
    # skip lives inside `if scraper_status[name]["running"]:` after the check.
    assert guard_idx < skip_idx, "skip is evaluated before the zombie check"
    assert skip_idx - guard_idx < 400, "guard and skip drifted apart — wiring changed"


def test_main_installs_a_watchdog_for_each_run() -> None:
    source = (_REPO_ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    assert "threading.Timer(_RUN_STALE_SECONDS" in source, "run watchdog missing"
    assert "_watchdog.cancel()" in source, "watchdog never cancelled — leaks a timer per run"
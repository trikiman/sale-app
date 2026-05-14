"""Tests for v1.26 Phase 84.5 — robust scrape freshness.

Pins three invariants that, together, keep the user-visible "Обновлено: N
мин" timestamp from exceeding 5 minutes:

1. ``scheduler_service.choose_due_job`` allows green-only to push the next
   full cycle by up to ``GREEN_OVERSHOOT_TOLERANCE_SECONDS``. The previous
   strict guard prevented green-only from ever fitting between full
   cycles, producing 5-7 min steady-state staleness.

2. ``scheduler_service.choose_due_job`` overrides the normal schedule and
   forces a green refresh when the green file mtime exceeds
   ``GREEN_STALL_THRESHOLD_SECONDS``. Belt-and-suspenders for silent
   scrape failures (e.g. browser crash mid-run, pool collapse) that would
   otherwise leave the file untouched until the next 5-min cycle tick.

3. ``backend.main._build_source_freshness`` uses a 5-minute staleness
   threshold by default (was 10 in v1.24). Aligns the banner trigger with
   the user's robustness target.
"""
from __future__ import annotations

import importlib
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Iterable

import pytest

# Ensure repo root is importable so we can grab `scheduler_service` and
# `backend.main` from the test runner.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ── scheduler_service.choose_due_job ────────────────────────────────────


def test_choose_due_job_allows_green_overshoot_up_to_tolerance() -> None:
    """v1.26 Phase 84.5: green-only is allowed to push next_all by up to
    ``GREEN_OVERSHOOT_TOLERANCE_SECONDS`` (default 60s).

    Pre-Phase 84.5 (`>= next_all`): with full-cycle interval 300s and
    green runtime ~110s, after a full cycle ends at T+240, the next_all
    is at T+300 and now+runtime (T+240+110=T+350) > T+300 → skip_green
    fires every time. Green-only intermediate runs were never possible.

    Post-Phase 84.5: tolerance of 60s lets green-only run when
    overshoot ≤ 60s. Same scenario: T+350 ≤ T+300+60 → green runs.
    """
    import scheduler_service as ss

    # Scenario: just finished a full cycle. now=T+240, next_all=T+300,
    # green-only is overdue (next_green=T+60), runtime=110s.
    # Overshoot = (240 + 110) - 300 = 50s, within tolerance.
    job = ss.choose_due_job(
        now_monotonic=240.0,
        next_all_due_at=300.0,
        next_green_due_at=60.0,
        estimated_green_runtime=110.0,
    )
    assert job == "green", (
        f"green-only should fit within 60s overshoot tolerance — got {job}"
    )


def test_choose_due_job_skips_green_when_overshoot_exceeds_tolerance() -> None:
    """Phase 84.5: skip_green still fires when green-only would push
    next_all by MORE than ``GREEN_OVERSHOOT_TOLERANCE_SECONDS``.

    Sanity check that the loosened guard isn't a no-op — full cycle
    cadence is still preserved if green-only would derail it badly.
    """
    import scheduler_service as ss

    # Now we're well past next_all and green runtime would push it by
    # 80s — beyond the 60s tolerance.
    job = ss.choose_due_job(
        now_monotonic=280.0,
        next_all_due_at=300.0,
        next_green_due_at=60.0,
        estimated_green_runtime=140.0,
    )
    assert job == "skip_green", (
        f"green-only must skip when overshoot exceeds tolerance — got {job}"
    )


def test_choose_due_job_returns_all_when_full_cycle_due() -> None:
    """Sanity: when both green-only and full-cycle are due, full-cycle
    wins because it includes green AND refreshes red/yellow.
    """
    import scheduler_service as ss

    job = ss.choose_due_job(
        now_monotonic=305.0,
        next_all_due_at=300.0,
        next_green_due_at=60.0,
        estimated_green_runtime=110.0,
    )
    assert job == "all"


def test_choose_due_job_returns_none_when_neither_due() -> None:
    """Sanity: scheduler sleeps when neither job is due."""
    import scheduler_service as ss

    job = ss.choose_due_job(
        now_monotonic=30.0,
        next_all_due_at=300.0,
        next_green_due_at=60.0,
        estimated_green_runtime=110.0,
    )
    assert job is None


def test_choose_due_job_stall_recovery_forces_green_when_file_too_old() -> None:
    """v1.26 Phase 84.5: when ``green_age_seconds`` exceeds
    ``GREEN_STALL_THRESHOLD_SECONDS`` (default 240s = 4 min), the
    scheduler ignores the normal schedule and forces a green refresh.

    Belt-and-suspenders for silent scrape failures: if the previous full
    cycle hung (browser crash, pool collapse mid-cycle, etc.) and never
    wrote green_products.json, the normal schedule would happily wait
    until the next 5-min tick. Stall recovery forces a green run as soon
    as the file age crosses the threshold, so the user-visible
    "Обновлено: N мин" never exceeds the 5-min target.
    """
    import scheduler_service as ss

    # Normal schedule says nothing is due — neither green nor all.
    # Without stall recovery this would return None.
    job = ss.choose_due_job(
        now_monotonic=10.0,
        next_all_due_at=300.0,
        next_green_due_at=60.0,
        estimated_green_runtime=110.0,
        green_age_seconds=ss.GREEN_STALL_THRESHOLD_SECONDS + 5,
    )
    assert job == "green", (
        f"stall recovery must force green when file age > "
        f"{ss.GREEN_STALL_THRESHOLD_SECONDS}s — got {job}"
    )


def test_choose_due_job_stall_recovery_prefers_full_cycle_if_due() -> None:
    """Phase 84.5: if both stall recovery is needed AND a full cycle is
    overdue, prefer ``"all"`` because it refreshes everything.
    """
    import scheduler_service as ss

    job = ss.choose_due_job(
        now_monotonic=305.0,
        next_all_due_at=300.0,
        next_green_due_at=60.0,
        estimated_green_runtime=110.0,
        green_age_seconds=ss.GREEN_STALL_THRESHOLD_SECONDS + 5,
    )
    assert job == "all", (
        f"stall recovery + full cycle due → must run full cycle — got {job}"
    )


def test_choose_due_job_no_stall_when_green_age_below_threshold() -> None:
    """Phase 84.5: green_age below threshold falls through to normal
    schedule logic.
    """
    import scheduler_service as ss

    # Green is fresh; normal schedule says nothing is due.
    job = ss.choose_due_job(
        now_monotonic=30.0,
        next_all_due_at=300.0,
        next_green_due_at=60.0,
        estimated_green_runtime=110.0,
        green_age_seconds=ss.GREEN_STALL_THRESHOLD_SECONDS - 30,
    )
    assert job is None, (
        f"green age below threshold must not trigger recovery — got {job}"
    )


def test_choose_due_job_handles_missing_green_file_gracefully() -> None:
    """Phase 84.5: ``green_age_seconds=None`` (file missing — fresh deploy
    scenario) must not crash and must fall through to normal schedule.
    """
    import scheduler_service as ss

    job = ss.choose_due_job(
        now_monotonic=305.0,
        next_all_due_at=300.0,
        next_green_due_at=60.0,
        estimated_green_runtime=110.0,
        green_age_seconds=None,
    )
    assert job == "all", "missing-file path must fall through to normal schedule"


# ── scheduler_service._green_file_age_seconds ──────────────────────────


def test_green_file_age_seconds_returns_age_when_file_exists(tmp_path, monkeypatch) -> None:
    """The helper reports `time.time() - mtime` when green_products.json
    exists. Used by the main loop to feed ``choose_due_job``.
    """
    import scheduler_service as ss

    fake_green = tmp_path / "green_products.json"
    fake_green.write_text("{}", encoding="utf-8")

    # Backdate mtime to 5 min ago
    backdate = time.time() - 300
    os.utime(fake_green, (backdate, backdate))

    monkeypatch.setattr(ss, "GREEN_PRODUCTS_PATH", str(fake_green))
    age = ss._green_file_age_seconds()
    assert age is not None
    assert 290 < age < 320, f"expected ~300s, got {age:.1f}s"


def test_green_file_age_seconds_returns_none_when_file_missing(tmp_path, monkeypatch) -> None:
    """The helper returns None when the file doesn't exist (fresh deploy)
    so callers can distinguish "no info" from "infinitely stale".
    """
    import scheduler_service as ss

    monkeypatch.setattr(
        ss, "GREEN_PRODUCTS_PATH", str(tmp_path / "does-not-exist.json")
    )
    assert ss._green_file_age_seconds() is None


# ── backend.main._build_source_freshness ───────────────────────────────


@pytest.fixture
def backend_with_isolated_data_dir(tmp_path, monkeypatch):
    """Yields the imported backend.main with DATA_DIR pointing to an empty
    tmp dir, so per-color file mtimes can be set deterministically.
    """
    monkeypatch.setenv("ADMIN_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_TOKEN", "test-token")
    # backend.main reads DATA_DIR at import time — re-import after we
    # patch the env, then patch DATA_DIR + PROPOSALS_PATH to tmp_path so
    # the test doesn't share state with the real data/ tree.
    if "backend.main" in sys.modules:
        del sys.modules["backend.main"]
    backend_main = importlib.import_module("backend.main")
    monkeypatch.setattr(backend_main, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(backend_main, "PROPOSALS_PATH", str(tmp_path / "proposals.json"))
    return backend_main


def _set_color_age(tmp_path: Path, color: str, age_minutes: float) -> None:
    """Create or touch ``<color>_products.json`` with mtime N minutes ago."""
    fp = tmp_path / f"{color}_products.json"
    fp.write_text("{}", encoding="utf-8")
    backdate = time.time() - age_minutes * 60
    os.utime(fp, (backdate, backdate))


def test_build_source_freshness_default_threshold_is_5_minutes(
    backend_with_isolated_data_dir, tmp_path
) -> None:
    """v1.26 Phase 84.5: default stale_minutes is 5 (was 10 in v1.24).

    A file 6 min old must be reported isStale=True with the default
    threshold. This pins the user-visible robustness target.
    """
    backend_main = backend_with_isolated_data_dir
    _set_color_age(tmp_path, "green", 6)
    _set_color_age(tmp_path, "red", 1)
    _set_color_age(tmp_path, "yellow", 2)

    freshness, stale_files, _latest = backend_main._build_source_freshness()
    assert freshness["green"]["isStale"] is True, (
        "6-min-old green file must be flagged stale at the new 5-min default"
    )
    assert freshness["red"]["isStale"] is False
    assert freshness["yellow"]["isStale"] is False
    assert any("green" in s for s in stale_files), (
        f"stale_files must include green — got {stale_files}"
    )


def test_build_source_freshness_marks_fresh_below_5_minutes(
    backend_with_isolated_data_dir, tmp_path
) -> None:
    """Phase 84.5: file 4 min old is still fresh under the 5-min default."""
    backend_main = backend_with_isolated_data_dir
    _set_color_age(tmp_path, "green", 4)
    _set_color_age(tmp_path, "red", 4)
    _set_color_age(tmp_path, "yellow", 4)

    freshness, stale_files, _ = backend_main._build_source_freshness()
    assert all(not info["isStale"] for info in freshness.values())
    assert stale_files == []


def test_build_source_freshness_explicit_threshold_still_works(
    backend_with_isolated_data_dir, tmp_path
) -> None:
    """Phase 84.5: callers can still override stale_minutes (for tests
    or future tuning). The default change must not break the parameter.
    """
    backend_main = backend_with_isolated_data_dir
    _set_color_age(tmp_path, "green", 7)
    _set_color_age(tmp_path, "red", 7)
    _set_color_age(tmp_path, "yellow", 7)

    # With threshold=10 all three are still fresh (legacy behavior).
    freshness, _, _ = backend_main._build_source_freshness(stale_minutes=10)
    assert all(not info["isStale"] for info in freshness.values())

    # With threshold=5 (the new default) all three are stale.
    freshness, _, _ = backend_main._build_source_freshness(stale_minutes=5)
    assert all(info["isStale"] for info in freshness.values())


def test_build_source_freshness_handles_missing_files(
    backend_with_isolated_data_dir, tmp_path
) -> None:
    """Phase 84.5: missing-file behavior unchanged — flagged with
    ``status='missing'`` and added to stale_files. Pin the contract since
    the default threshold change touches the same function.
    """
    backend_main = backend_with_isolated_data_dir
    # Don't create any files — all three are missing.
    freshness, stale_files, latest_mtime = backend_main._build_source_freshness()
    for color in ("green", "red", "yellow"):
        assert freshness[color]["exists"] is False
        assert freshness[color]["status"] == "missing"
        assert freshness[color]["isStale"] is True
    assert latest_mtime == 0.0
    assert sorted(stale_files) == ["green (missing)", "red (missing)", "yellow (missing)"]

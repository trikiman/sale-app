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
import json
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


def test_build_source_freshness_default_thresholds_are_per_color(
    backend_with_isolated_data_dir, tmp_path
) -> None:
    """v1.26 Phase 84.7: default thresholds are per-color (green=5, red=5,
    yellow=10). The previous uniform 5-min threshold (Phase 84.5) put red
    and yellow at the cycle-cadence edge — saves landing every ~5 min
    meant the stale flag flickered on/off right around the threshold.
    Yellow gets the larger 10-min budget; green and red stay tight at 5.
    """
    backend_main = backend_with_isolated_data_dir
    # Each color exactly 6 min old.
    _set_color_age(tmp_path, "green", 6)
    _set_color_age(tmp_path, "red", 6)
    _set_color_age(tmp_path, "yellow", 6)

    freshness, stale_files, _latest = backend_main._build_source_freshness()
    assert freshness["green"]["isStale"] is True, "green > 5min must be stale"
    assert freshness["red"]["isStale"] is True, "red > 5min must be stale"
    assert freshness["yellow"]["isStale"] is False, (
        "yellow ≤ 10min must NOT be stale (Phase 84.7 gives yellow 10-min headroom)"
    )
    assert freshness["yellow"]["staleThresholdMinutes"] == 10
    assert freshness["green"]["staleThresholdMinutes"] == 5
    assert freshness["red"]["staleThresholdMinutes"] == 5
    # Only green + red surface in stale_files; yellow is fresh under 10.
    assert sorted([s.split()[0] for s in stale_files]) == ["green", "red"]


def test_build_source_freshness_yellow_stale_only_above_10(
    backend_with_isolated_data_dir, tmp_path
) -> None:
    """Phase 84.7: yellow at 9.5 min is fresh, at 11 min is stale."""
    backend_main = backend_with_isolated_data_dir
    _set_color_age(tmp_path, "green", 1)
    _set_color_age(tmp_path, "red", 1)
    _set_color_age(tmp_path, "yellow", 9.5)

    freshness, stale_files, _ = backend_main._build_source_freshness()
    assert freshness["yellow"]["isStale"] is False
    assert stale_files == []

    _set_color_age(tmp_path, "yellow", 11)
    freshness, stale_files, _ = backend_main._build_source_freshness()
    assert freshness["yellow"]["isStale"] is True


def test_build_source_freshness_marks_fresh_below_thresholds(
    backend_with_isolated_data_dir, tmp_path
) -> None:
    """Phase 84.7: each color fresh when below its own threshold."""
    backend_main = backend_with_isolated_data_dir
    _set_color_age(tmp_path, "green", 4)
    _set_color_age(tmp_path, "red", 4)
    _set_color_age(tmp_path, "yellow", 9)

    freshness, stale_files, _ = backend_main._build_source_freshness()
    assert all(not info["isStale"] for info in freshness.values())
    assert stale_files == []


def test_build_source_freshness_legacy_stale_minutes_kwarg_overrides_all_colors(
    backend_with_isolated_data_dir, tmp_path
) -> None:
    """Phase 84.7: ``stale_minutes`` kwarg (legacy) applies a single
    threshold to all 3 colors — kept for ad-hoc admin scripts and back-compat.
    ``stale_thresholds`` dict (new) takes precedence when both are given.
    """
    backend_main = backend_with_isolated_data_dir
    _set_color_age(tmp_path, "green", 7)
    _set_color_age(tmp_path, "red", 7)
    _set_color_age(tmp_path, "yellow", 7)

    # Legacy single-int wins when only it is provided.
    freshness, _, _ = backend_main._build_source_freshness(stale_minutes=10)
    assert all(not info["isStale"] for info in freshness.values()), (
        "stale_minutes=10 must keep all 7-min files fresh"
    )

    freshness, _, _ = backend_main._build_source_freshness(stale_minutes=5)
    assert all(info["isStale"] for info in freshness.values()), (
        "stale_minutes=5 must flag all 7-min files stale"
    )

    # Per-color dict beats the legacy int when both are passed.
    freshness, _, _ = backend_main._build_source_freshness(
        stale_minutes=5,
        stale_thresholds={"yellow": 30},
    )
    assert freshness["green"]["isStale"] is True, "green still uses default 5"
    assert freshness["red"]["isStale"] is True, "red still uses default 5"
    assert freshness["yellow"]["isStale"] is False, (
        "yellow override to 30 must beat the stale_minutes=5 legacy kwarg"
    )


def test_build_source_freshness_partial_dict_falls_back_to_defaults(
    backend_with_isolated_data_dir, tmp_path
) -> None:
    """Phase 84.7: partial dict only overrides the named colors; others
    fall back to ``DEFAULT_STALE_THRESHOLDS_MINUTES``.
    """
    backend_main = backend_with_isolated_data_dir
    _set_color_age(tmp_path, "green", 6)   # default 5 → stale
    _set_color_age(tmp_path, "red", 6)     # default 5 → stale
    _set_color_age(tmp_path, "yellow", 6)  # default 10 → fresh

    # Override only green to 30 — red and yellow keep their defaults.
    freshness, _, _ = backend_main._build_source_freshness(
        stale_thresholds={"green": 30},
    )
    assert freshness["green"]["isStale"] is False, "green override 30 → fresh"
    assert freshness["red"]["isStale"] is True, "red default 5 → stale at 6m"
    assert freshness["yellow"]["isStale"] is False, "yellow default 10 → fresh at 6m"


def test_build_source_freshness_handles_missing_files(
    backend_with_isolated_data_dir, tmp_path
) -> None:
    """Phase 84.7: missing-file behavior unchanged — flagged with
    ``status='missing'`` and added to stale_files. Pin the contract since
    the per-color threshold change touches the same function.
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


# ── backend.main._compute_empty_reason ─────────────────────────────────


def test_compute_empty_reason_fresh_deploy_when_all_files_missing(
    backend_with_isolated_data_dir, tmp_path
) -> None:
    """v1.26 Phase 85 UX-EMPTY-01: when no source file exists, the empty
    products list signals a fresh deploy — scrapers haven't run yet.
    Frontend renders 'Сборщик данных запускается' copy.
    """
    backend_main = backend_with_isolated_data_dir
    freshness, _, _ = backend_main._build_source_freshness()
    # All colors `exists: false` (tmp_path is empty).
    assert backend_main._compute_empty_reason(freshness) == "fresh_deploy"


def test_compute_empty_reason_all_stale_when_every_file_past_threshold(
    backend_with_isolated_data_dir, tmp_path
) -> None:
    """Phase 85: when every source file exists but every isStale=true,
    return 'all_stale'. Frontend renders 'Идёт восстановление' copy.
    """
    backend_main = backend_with_isolated_data_dir
    # Give all 3 colors files that are well past their thresholds.
    _set_color_age(tmp_path, "green", 30)   # 30m > 5m threshold
    _set_color_age(tmp_path, "red", 30)     # 30m > 5m threshold
    _set_color_age(tmp_path, "yellow", 30)  # 30m > 10m threshold

    freshness, _, _ = backend_main._build_source_freshness()
    for c in ("green", "red", "yellow"):
        assert freshness[c]["isStale"] is True
    assert backend_main._compute_empty_reason(freshness) == "all_stale"


def test_compute_empty_reason_genuinely_empty_when_files_fresh(
    backend_with_isolated_data_dir, tmp_path
) -> None:
    """Phase 85: when files are fresh but the merged products list is
    empty, that's a real 'VkusVill has no active sales' case. Frontend
    renders 'Сейчас нет активных акций' copy.
    """
    backend_main = backend_with_isolated_data_dir
    _set_color_age(tmp_path, "green", 1)
    _set_color_age(tmp_path, "red", 1)
    _set_color_age(tmp_path, "yellow", 1)

    freshness, _, _ = backend_main._build_source_freshness()
    assert all(not freshness[c]["isStale"] for c in ("green", "red", "yellow"))
    assert backend_main._compute_empty_reason(freshness) == "genuinely_empty"


def test_compute_empty_reason_partial_freshness_is_genuinely_empty(
    backend_with_isolated_data_dir, tmp_path
) -> None:
    """Phase 85: if at least one source is fresh, the empty list is NOT
    a fresh-deploy or all-stale case — fall through to genuinely_empty.
    Some scrapes succeeded, they just returned no products.
    """
    backend_main = backend_with_isolated_data_dir
    _set_color_age(tmp_path, "green", 30)   # stale
    _set_color_age(tmp_path, "red", 1)      # fresh
    _set_color_age(tmp_path, "yellow", 30)  # stale (10m threshold)

    freshness, _, _ = backend_main._build_source_freshness()
    assert backend_main._compute_empty_reason(freshness) == "genuinely_empty"



# ── scheduler_service._pool_watchdog_loop ────────────────────────────────


def test_pool_watchdog_triggers_refresh_when_pool_dead_past_grace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """v1.27: watchdog calls ensure_pool() once observed pool=0 has
    persisted for ≥ POOL_DEAD_GRACE_SECONDS. Internal throttle in
    VlessProxyManager.ensure_pool() prevents hammering."""
    import threading
    import scheduler_service as ss

    # Force tight grace + interval so the test runs in ~3s.
    monkeypatch.setattr(ss, "POOL_WATCHDOG_INTERVAL_S", 1, raising=True)
    monkeypatch.setattr(ss, "POOL_DEAD_GRACE_SECONDS", 1, raising=True)

    # Dynamic pool always empty (watchdog gates on _dynamic_pool_size now).
    monkeypatch.setattr(ss, "_dynamic_pool_size", lambda: 0, raising=True)

    # Capture ensure_pool() calls.
    refresh_calls: list[int] = []

    class _StubManager:
        def __init__(self, **kwargs) -> None:
            pass

        def ensure_pool(self) -> int:
            refresh_calls.append(1)
            return 5  # simulate recovery so the next iteration sees recovery

    # Replace the import target lazily — the watchdog imports inline.
    import vless.manager as vm_mod
    monkeypatch.setattr(vm_mod, "VlessProxyManager", _StubManager, raising=True)

    stop = threading.Event()
    t = threading.Thread(target=ss._pool_watchdog_loop, args=(stop,), daemon=True)
    t.start()
    # Give the watchdog enough wall time to: tick 1 (grace start),
    # tick 2 (grace satisfied → refresh).
    time.sleep(3.5)
    stop.set()
    t.join(timeout=2.0)

    assert refresh_calls, (
        "watchdog should have called ensure_pool() at least once "
        "after pool stayed dead past grace"
    )


def test_pool_watchdog_skips_refresh_when_pool_healthy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No refresh attempts while pool stays non-empty."""
    import threading
    import scheduler_service as ss

    monkeypatch.setattr(ss, "POOL_WATCHDOG_INTERVAL_S", 1, raising=True)
    monkeypatch.setattr(ss, "POOL_DEAD_GRACE_SECONDS", 1, raising=True)
    monkeypatch.setattr(ss, "_dynamic_pool_size", lambda: 5, raising=True)

    refresh_calls: list[int] = []

    class _StubManager:
        def __init__(self, **kwargs) -> None:
            pass

        def ensure_pool(self) -> int:
            refresh_calls.append(1)
            return 5

    import vless.manager as vm_mod
    monkeypatch.setattr(vm_mod, "VlessProxyManager", _StubManager, raising=True)

    stop = threading.Event()
    t = threading.Thread(target=ss._pool_watchdog_loop, args=(stop,), daemon=True)
    t.start()
    time.sleep(3.0)
    stop.set()
    t.join(timeout=2.0)

    assert not refresh_calls, (
        f"watchdog should not refresh when pool healthy — got {len(refresh_calls)} calls"
    )



# ── v1.27 follow-up #2: quarantine auto-clear ───────────────────────────


def test_pool_watchdog_clears_quarantine_when_bloated_during_outage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When pool=0 AND quarantine size ≥ threshold sustained for the grace
    window, watchdog must call quarantine.clear_all() to release hosts
    back into the candidate pipeline. This is the 3-times-recurring
    pool-starvation pattern (May 17 / 22 / 29) we couldn't fix with just
    refresh-on-dead because quarantine kept hoarding candidates."""
    import threading
    import scheduler_service as ss

    monkeypatch.setattr(ss, "POOL_WATCHDOG_INTERVAL_S", 1, raising=True)
    monkeypatch.setattr(ss, "POOL_DEAD_GRACE_SECONDS", 1, raising=True)
    monkeypatch.setattr(ss, "QUARANTINE_BURST_THRESHOLD", 5, raising=True)
    monkeypatch.setattr(ss, "QUARANTINE_BURST_GRACE_SECONDS", 1, raising=True)
    monkeypatch.setattr(ss, "QUARANTINE_CLEAR_COOLDOWN_S", 1, raising=True)
    monkeypatch.setattr(ss, "_dynamic_pool_size", lambda: 0, raising=True)

    # Stub out ensure_pool to always return 0 so pool stays dead.
    import vless.manager as vm_mod

    class _StubManager:
        def __init__(self, **kwargs) -> None:
            pass

        def ensure_pool(self) -> int:
            return 0

    monkeypatch.setattr(vm_mod, "VlessProxyManager", _StubManager, raising=True)

    # Quarantine: 100 hosts (well above threshold of 5). Track clear() calls.
    import vless.quarantine as q_mod

    clear_calls: list[int] = []

    monkeypatch.setattr(q_mod, "snapshot", lambda: {"count": 100}, raising=True)
    monkeypatch.setattr(
        q_mod, "clear_all", lambda: clear_calls.append(1), raising=True
    )

    stop = threading.Event()
    t = threading.Thread(target=ss._pool_watchdog_loop, args=(stop,), daemon=True)
    t.start()
    # Wait long enough for: tick 1 detect bloat, tick 2 grace satisfied,
    # clear fires. Give a generous 4s buffer.
    time.sleep(4.0)
    stop.set()
    t.join(timeout=2.0)

    assert clear_calls, (
        "watchdog should have called quarantine.clear_all() at least once "
        "after pool stayed dead with bloated quarantine past grace"
    )


def test_pool_watchdog_skips_quarantine_clear_when_pool_healthy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quarantine bloat alone doesn't trigger clear — pool must also be dead.
    A healthy pool with big quarantine is fine (good probes admitted, bad
    ones quarantined — that's exactly the design)."""
    import threading
    import scheduler_service as ss

    monkeypatch.setattr(ss, "POOL_WATCHDOG_INTERVAL_S", 1, raising=True)
    monkeypatch.setattr(ss, "QUARANTINE_BURST_THRESHOLD", 5, raising=True)
    monkeypatch.setattr(ss, "QUARANTINE_BURST_GRACE_SECONDS", 1, raising=True)
    monkeypatch.setattr(ss, "_dynamic_pool_size", lambda: 5, raising=True)  # HEALTHY

    import vless.quarantine as q_mod

    clear_calls: list[int] = []
    monkeypatch.setattr(q_mod, "snapshot", lambda: {"count": 200}, raising=True)
    monkeypatch.setattr(
        q_mod, "clear_all", lambda: clear_calls.append(1), raising=True
    )

    stop = threading.Event()
    t = threading.Thread(target=ss._pool_watchdog_loop, args=(stop,), daemon=True)
    t.start()
    time.sleep(3.5)
    stop.set()
    t.join(timeout=2.0)

    assert not clear_calls, (
        f"watchdog must NOT clear quarantine when pool is healthy; got {len(clear_calls)} clear calls"
    )


def test_pool_watchdog_quarantine_clear_respects_cooldown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After firing once, watchdog must wait QUARANTINE_CLEAR_COOLDOWN_S
    before firing again — even if pool stays dead and quarantine refills.
    Prevents a tight loop when the network is genuinely down."""
    import threading
    import scheduler_service as ss

    monkeypatch.setattr(ss, "POOL_WATCHDOG_INTERVAL_S", 1, raising=True)
    monkeypatch.setattr(ss, "POOL_DEAD_GRACE_SECONDS", 1, raising=True)
    monkeypatch.setattr(ss, "QUARANTINE_BURST_THRESHOLD", 5, raising=True)
    monkeypatch.setattr(ss, "QUARANTINE_BURST_GRACE_SECONDS", 1, raising=True)
    # Long cooldown so we expect EXACTLY one clear within the test window.
    monkeypatch.setattr(ss, "QUARANTINE_CLEAR_COOLDOWN_S", 10000, raising=True)
    monkeypatch.setattr(ss, "_dynamic_pool_size", lambda: 0, raising=True)

    import vless.manager as vm_mod

    class _StubManager:
        def __init__(self, **kwargs) -> None:
            pass

        def ensure_pool(self) -> int:
            return 0

    monkeypatch.setattr(vm_mod, "VlessProxyManager", _StubManager, raising=True)

    import vless.quarantine as q_mod

    clear_calls: list[int] = []
    monkeypatch.setattr(q_mod, "snapshot", lambda: {"count": 100}, raising=True)
    monkeypatch.setattr(
        q_mod, "clear_all", lambda: clear_calls.append(1), raising=True
    )

    stop = threading.Event()
    t = threading.Thread(target=ss._pool_watchdog_loop, args=(stop,), daemon=True)
    t.start()
    time.sleep(5.0)  # 5 watchdog ticks; without cooldown would fire ~3-5x
    stop.set()
    t.join(timeout=2.0)

    assert len(clear_calls) == 1, (
        f"cooldown must limit clears to exactly 1 within window; got {len(clear_calls)}"
    )


# ── v1.27.2 root-cause fix: bridge-aware _is_pool_dead ──────────────────


def test_is_pool_dead_false_when_dynamic_pool_has_nodes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dynamic pool with ≥1 node → not dead (unchanged behavior)."""
    import scheduler_service as ss

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "vless_pool.json").write_text(
        json.dumps({"nodes": [{"host": "1.2.3.4", "port": 443}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(ss, "DATA_DIR", str(data_dir), raising=True)
    assert ss._is_pool_dead() is False


def test_is_pool_dead_false_when_pool_empty_but_manual_seeds_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """THE ROOT-CAUSE FIX: dynamic pool empty BUT manual seeds present →
    NOT dead. Previously this returned True and caused scrapers to skip
    even though the manual-seed bridge routes VkusVill traffic fine."""
    import scheduler_service as ss

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "vless_pool.json").write_text(
        json.dumps({"nodes": []}), encoding="utf-8"
    )
    monkeypatch.setattr(ss, "DATA_DIR", str(data_dir), raising=True)
    monkeypatch.setattr(ss, "_has_manual_seeds", lambda: True, raising=True)
    assert ss._is_pool_dead() is False, (
        "empty dynamic pool + manual seeds must NOT report dead — that was "
        "the false-starvation bug"
    )


def test_is_pool_dead_true_only_when_pool_empty_and_no_manual_seeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Genuine no-capacity: empty dynamic pool AND no manual seeds → dead."""
    import scheduler_service as ss

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "vless_pool.json").write_text(
        json.dumps({"nodes": []}), encoding="utf-8"
    )
    monkeypatch.setattr(ss, "DATA_DIR", str(data_dir), raising=True)
    monkeypatch.setattr(ss, "_has_manual_seeds", lambda: False, raising=True)
    assert ss._is_pool_dead() is True


def test_is_pool_dead_missing_file_falls_back_to_manual_seeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No pool file at all → still alive if manual seeds exist."""
    import scheduler_service as ss

    data_dir = tmp_path / "data"
    data_dir.mkdir()  # no vless_pool.json written
    monkeypatch.setattr(ss, "DATA_DIR", str(data_dir), raising=True)
    monkeypatch.setattr(ss, "_has_manual_seeds", lambda: True, raising=True)
    assert ss._is_pool_dead() is False


def test_dynamic_pool_size_counts_only_dynamic_nodes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_dynamic_pool_size reports the raw dynamic count, ignoring manual
    seeds — the watchdog uses it to keep growing dynamic diversity."""
    import scheduler_service as ss

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "vless_pool.json").write_text(
        json.dumps({"nodes": [{"host": "a"}, {"host": "b"}, {"host": "c"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(ss, "DATA_DIR", str(data_dir), raising=True)
    assert ss._dynamic_pool_size() == 3
    # Manual seeds don't inflate the dynamic count.
    monkeypatch.setattr(ss, "_has_manual_seeds", lambda: True, raising=True)
    assert ss._dynamic_pool_size() == 3


def test_has_manual_seeds_reflects_module_constant() -> None:
    """_has_manual_seeds mirrors vless.manual_seeds.MANUAL_TROJAN_SEEDS."""
    import scheduler_service as ss
    from vless.manual_seeds import MANUAL_TROJAN_SEEDS

    expected = len(MANUAL_TROJAN_SEEDS) > 0
    assert ss._has_manual_seeds() is expected

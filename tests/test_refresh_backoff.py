"""An empty refresh must not be retried every 60 s.

Measured 2026-11-17: with the pool at 0 the watchdog re-ran the full refresh
every 60 s, and each run costs ~2.5 min of xray probing on a 1 vCPU box —
competing with the green cycles for the only core.
"""
from __future__ import annotations

from vless import manager


def test_backoff_is_longer_than_the_normal_interval() -> None:
    assert manager.REFRESH_EMPTY_BACKOFF_S >= 10 * manager.REFRESH_MIN_INTERVAL_S


def test_backoff_constant_is_bounded() -> None:
    # Waiting hours would hide a genuinely recoverable source.
    assert manager.REFRESH_EMPTY_BACKOFF_S <= 3600


import json

from vless.manager import VlessProxyManager


def _pm(tmp_path) -> VlessProxyManager:
    return VlessProxyManager(
        pool_path=tmp_path / "vless_pool.json",
        log_func=lambda *_: None,
        register_atexit=False,
    )


def test_streak_survives_a_new_manager_instance(tmp_path) -> None:
    """The exact bug: a new manager must still see the previous streak."""
    first = _pm(tmp_path)
    first._save_backoff(2)
    second = _pm(tmp_path)
    assert second._load_backoff()[0] == 2
    assert (tmp_path / "vless_backoff.json").exists()


def test_missing_or_corrupt_backoff_file_is_not_fatal(tmp_path) -> None:
    pm = _pm(tmp_path)
    assert pm._load_backoff() == (0, 0.0)
    (tmp_path / "vless_backoff.json").write_text("{not json", encoding="utf-8")
    assert pm._load_backoff() == (0, 0.0)


def test_ensure_pool_throttles_after_two_empty_refreshes(tmp_path, monkeypatch) -> None:
    pm = _pm(tmp_path)
    calls = {"n": 0}

    def fake_refresh(exclude=None):
        calls["n"] += 1
        return 0

    monkeypatch.setattr(pm, "refresh_proxy_list", fake_refresh)
    monkeypatch.setattr(pm, "pool_count", lambda: 0)
    monkeypatch.setattr(pm, "is_cache_stale", lambda: False)
    monkeypatch.setattr(pm, "_monotonic", lambda: 0.0)

    pm.ensure_pool()  # first empty refresh -> streak 1
    assert calls["n"] == 1
    # age the attempt past the 60 s window so the next call may refresh again
    pm._backoff_path.write_text(json.dumps({"empty_streak": 1, "last_attempt": 0.0}))
    pm.ensure_pool()  # second empty refresh -> streak 2
    assert calls["n"] == 2
    pm.ensure_pool()  # must now be throttled for 30 min, no third refresh
    assert calls["n"] == 2, "empty streak >= 2 must back off instead of refreshing"
    saved = json.loads(pm._backoff_path.read_text(encoding="utf-8"))
    assert saved["empty_streak"] == 2


def test_a_successful_admission_resets_the_streak(tmp_path, monkeypatch) -> None:
    pm = _pm(tmp_path)
    # a real streak, but the attempt long ago — so the backoff does not hide it
    pm._backoff_path.write_text(json.dumps({"empty_streak": 3, "last_attempt": 0.0}))
    monkeypatch.setattr(pm, "refresh_proxy_list", lambda exclude=None: 2)
    monkeypatch.setattr(pm, "pool_count", lambda: 2)
    monkeypatch.setattr(pm, "is_cache_stale", lambda: False)
    monkeypatch.setattr(pm, "_monotonic", lambda: 0.0)
    pm.ensure_pool()
    assert pm._load_backoff()[0] == 0

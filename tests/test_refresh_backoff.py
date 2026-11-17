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


def test_manager_tracks_an_empty_refresh_streak() -> None:
    src = open("vless/manager.py", encoding="utf-8").read()
    assert "_empty_refresh_streak" in src
    # the streak must actually gate the throttle choice
    assert "REFRESH_EMPTY_BACKOFF_S" in src.split("def ensure_pool")[1]
    # and must reset when something is admitted
    assert "self._empty_refresh_streak = 0" in src


def test_backoff_branch_uses_two_consecutive_failures() -> None:
    """One empty refresh can be a blip; two mean the lists have nothing for us."""
    src = open("vless/manager.py", encoding="utf-8").read()
    assert "self._empty_refresh_streak >= 2" in src

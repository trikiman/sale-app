"""The admission probe must budget for a 380 KB body through a fresh tunnel.

Measured 2026-11-17: 102 of 152 candidates opened TCP, all 152 were rejected as
`probe_error`, and the pool stayed at 0 for hours. The probe requires the real
homepage (>20 KB) and was given 8 s on a 1 vCPU box — not enough to transfer it.
"""
from __future__ import annotations

from vless import manager


def test_probe_timeout_covers_a_full_homepage_transfer() -> None:
    assert manager.PROBE_TIMEOUT >= 15, (
        "probe budget below 15 s re-introduces the 2026-11-17 zero-admission bug"
    )


def test_probe_timeout_stays_bounded() -> None:
    # The probe runs per candidate inside a parallel admission pass; an unbounded
    # budget would stall the whole refresh.
    assert manager.PROBE_TIMEOUT <= 40


def test_probe_uses_the_real_catalog_url() -> None:
    # The vpn-detected redirect is only observable on the real domain.
    assert "vkusvill.ru" in manager.VKUSVILL_URL


def test_body_floor_still_guards_against_error_pages() -> None:
    # Keeping the 20 KB floor is WHY the budget had to grow; both must stay.
    src = open("vless/manager.py", encoding="utf-8").read()
    assert "20_000" in src
    assert "vpn-detected" in src

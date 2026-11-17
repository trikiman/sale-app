"""Every CDP navigation needs a deadline.

Measured 2026-11-17: the run logged "Loaded 48/48 cookies via CDP" at 03:55:42 and
then printed nothing for seven minutes until the 420 s watchdog killed it. The
page.get() call was awaiting a tunnel that never answered (pool 0-1 nodes). An
unbounded navigation turns one bad exit into a lost cycle and a false gap in the
uptime series.
"""
from __future__ import annotations


def _src() -> str:
    return open("scrape_green.py", encoding="utf-8").read()


def test_deadline_constant_is_bounded() -> None:
    src = _src()
    assert "PAGE_GET_TIMEOUT_S" in src
    value = int(src.split("PAGE_GET_TIMEOUT_S = ")[1].split("\n")[0])
    assert 30 <= value <= 180, f"navigation deadline {value}s is not sane"


def test_no_unbounded_page_get_remains() -> None:
    src = _src()
    leftovers = [
        line.strip()
        for line in src.splitlines()
        if "await page.get(" in line
    ]
    assert not leftovers, f"unbounded navigation(s) left: {leftovers}"


def test_helper_wraps_in_wait_for() -> None:
    src = _src()
    helper = src.split("async def _page_get(")[1].split("async def _js(")[0]
    assert "asyncio.wait_for" in helper
    assert "TimeoutError" in helper


def test_all_navigation_sites_use_the_helper() -> None:
    src = _src()
    assert src.count("await _page_get(page,") >= 3

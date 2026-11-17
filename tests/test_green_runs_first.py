"""GREEN must be the first scraper in the full cycle.

Measured 2026-11-17: green got its turn only after red and yellow. A hung yellow
(420 s watchdog) plus its retry starved it entirely — `green_uptime.jsonl` had no
record between 03:10 and 03:28 while the scheduler was busy the whole time. Green
is what the milestone measures (and what the UI shows), so it runs first; red and
yellow feed history and tolerate being late.
"""
from __future__ import annotations


def _src() -> str:
    return open("scheduler_service.py", encoding="utf-8").read()


def _full_cycle_scrapers() -> str:
    src = _src()
    start = src.find("scrapers = [")
    return src[start : src.find("]", start)]


def test_green_is_the_first_scraper_in_the_full_cycle() -> None:
    block = _full_cycle_scrapers()
    order = [line for line in block.splitlines() if "scrape_" in line]
    assert "scrape_green.py" in order[0], f"green must run first, got: {order}"


def test_all_three_scrapers_still_run() -> None:
    block = _full_cycle_scrapers()
    for script in ("scrape_green.py", "scrape_red.py", "scrape_yellow.py"):
        assert script in block

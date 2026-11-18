"""Admin status must not claim the scrapers never ran.

`/admin/status` returned `scraper_status` with every field `None` while cycles were
finishing every few minutes: that dict is filled by the scraper runner inside the
backend process, but scraping runs in the separate scheduler service. Reading the
empty block as "скрейперы не запускались" is exactly the false alarm the operator
keeps catching.

The endpoint now back-fills `last_run`/`last_output` from `cycleState`, which the
scheduler writes after every cycle.
"""
from __future__ import annotations


def _src() -> str:
    return open("backend/main.py", encoding="utf-8").read()


def test_status_backfills_from_cycle_state() -> None:
    src = _src()
    block = src.split('"scrapers": scraper_status,')[0]
    tail = block[-2500:]
    assert "_cs_sources" in tail, "no cycleState fallback before returning scrapers"
    assert 'if _row.get("last_run") is None:' in tail
    assert '_info.get("status_text")' in tail


def test_fallback_covers_merge_and_notifier() -> None:
    src = _src()
    tail = src.split('"scrapers": scraper_status,')[0][-2500:]
    assert 'for _extra in ("merge", "notifier")' in tail


def test_fallback_never_overwrites_real_runs() -> None:
    src = _src()
    tail = src.split('"scrapers": scraper_status,')[0][-2500:]
    # Both assignments must be guarded, or a real in-process run would be clobbered.
    assert tail.count("is None") + tail.count("if not _row.get") >= 2

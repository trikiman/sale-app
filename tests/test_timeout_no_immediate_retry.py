"""A hung scraper must not be retried immediately.

Measured 2026-11-17: `TIMEOUT scrape_yellow.py killed after 420s` fired twice in a
row (02:07, 02:29) and a `YELLOW-RETRY` was still running at 03:26, while
`green_uptime.jsonl` had no record between 03:10 and 03:28. The cycle is
sequential (RED -> YELLOW -> GREEN), so a hung run plus its immediate retry
occupies ~14 minutes and the green pass never gets its turn.

A timeout means the run hung, not that the proxy misbehaved — the next cycle can
try again with a fresh Chrome.
"""
from __future__ import annotations


def _src() -> str:
    return open("scheduler_service.py", encoding="utf-8").read()


def _timeout_branch() -> str:
    """The per-scraper branch, not any earlier `code == -2` check."""
    src = _src()
    after_call = src.split("code = run_script(script, tag)")[1]
    return after_call.split("if code == -2:")[1].split("elif code == 1:")[0]


def test_timeout_branch_skips_the_retry() -> None:
    timeout_branch = _timeout_branch()
    assert "skipping the retry" in timeout_branch
    assert "run_script(script, f\"{tag}-RETRY\")" not in timeout_branch


def test_failed_branch_keeps_the_retry() -> None:
    src = _src()
    failed_branch = src.split("elif code == 1:")[1]
    assert 'run_script(script, f"{tag}-RETRY")' in failed_branch, (
        "a real failure (exit 1) is still worth one retry on a different proxy"
    )


def test_timeout_branch_still_frees_chrome() -> None:
    assert "_kill_all_scraper_chrome()" in _timeout_branch()

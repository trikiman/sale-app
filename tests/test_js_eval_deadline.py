"""A hung CDP evaluate must not produce 15 minutes of silence.

Measured 2026-11-18: two runs in a row were killed by the 420 s silence watchdog at
1027 s and 864 s, both right after `Loaded 48/48 cookies via CDP`. That opened a
69.4-minute gap in the uptime series (the only non-historical gap). The cause is a
`page.evaluate` that never returned: `_js` had no deadline, and the watchdog only
fires on silence, so a single stalled CDP round-trip looks like a dead cycle.

`_js` now wraps `page.evaluate` in a 45 s `asyncio.wait_for`, and TimeoutError is
treated as a dead-socket error so `_safe_js` re-acquires a handle and retries.
"""
from __future__ import annotations


def _src() -> str:
    return open("scrape_green.py", encoding="utf-8").read()


def test_eval_deadline_exists_and_is_sane() -> None:
    src = _src()
    assert "JS_EVAL_TIMEOUT_S" in src
    value = int(src.split("JS_EVAL_TIMEOUT_S = ")[1].split("\n")[0])
    assert 15 <= value <= 120, f"eval deadline {value}s is not sane"


def test_evaluate_is_wrapped_in_wait_for() -> None:
    src = _src()
    body = src.split("async def _js(page, script):")[1].split("async def ")[0]
    assert "asyncio.wait_for" in body
    assert "page.evaluate(script)" in body


def test_timeout_counts_as_a_dead_socket_so_retries_apply() -> None:
    src = _src()
    dead = src.split("def _is_dead_ws_error")[1].split("async def")[0]
    assert '"TimeoutError"' in dead, (
        "without this, the first hung evaluate kills the cycle instead of retrying"
    )

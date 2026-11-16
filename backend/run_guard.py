"""Run-lock zombie detection (v1.30 GREEN-UP-02).

`backend/main.py` starts each scraper in a worker thread that marks
`scraper_status[name]["running"] = True` and clears it in a `finally` block. The
worker spends most of its life blocked on `for line in proc.stdout`; when the
child process is alive but silent (Chrome died mid-cycle and the scraper sits in
a socket read) that loop never returns, the `finally` never runs, and the flag
stays `True` forever.

Consequence, measured 2026-11-15: every scheduler tick logged
"Already running, skipping" and `green_products.json` went 42 minutes untouched —
long past the staleness threshold that used to hide all green cards.

This module holds the decision itself, free of threading/subprocess imports, so
it can be tested without FastAPI or python-telegram-bot.
"""

from __future__ import annotations

# A green cycle is capped at 300 s by the scheduler. Three times that is
# unambiguously a dead run, not a slow one.
DEFAULT_STALE_SECONDS = 900


def is_zombie_run(
    started_at: float | None,
    now: float,
    stale_seconds: int = DEFAULT_STALE_SECONDS,
) -> bool:
    """True when a `running` flag has outlived its usefulness.

    ``started_at is None`` with the flag set means the timestamp was never
    recorded (state produced before this guard existed) — treat as a zombie so
    one upgrade clears the stuck flag instead of requiring a restart.
    """
    if not started_at:
        return True
    return (now - started_at) > stale_seconds
"""Every green run must reach the soak, including the retry pass.

Measured 2026-11-17: the scheduler calls ``run_script(script, "GREEN-RETRY")`` on
the retry path, while the recorder was gated on a strict ``tag == "GREEN"``. The
soak therefore stayed at 68 records while cycles kept finishing every few minutes
and ``green_products.json`` kept updating — the recorder was silently skipping the
runs that matter most (the dropped ones are exactly the ones that fail first).
"""
from __future__ import annotations


def _src() -> str:
    return open("scheduler_service.py", encoding="utf-8").read()


def test_recorder_accepts_the_retry_tag() -> None:
    src = _src()
    assert 'tag.upper().startswith("GREEN")' in src, (
        "a strict tag == 'GREEN' drops every retried cycle from the soak"
    )
    assert 'if tag == "GREEN":' not in src


def test_retry_path_still_uses_the_suffixed_tag() -> None:
    # If the retry tag ever changes shape, the recorder must keep matching it.
    src = _src()
    assert 'f"{tag}-RETRY"' in src


def test_recorder_is_called_after_wait() -> None:
    """The record must follow proc.wait(), or the exit code is undefined."""
    src = _src()
    record_at = src.find("_record_green_uptime(\n            ok=(proc.returncode == 0)")
    wait_at = src.find("proc.wait(timeout=10)")
    assert wait_at != -1 and record_at != -1
    assert wait_at < record_at, "recording before the child exits yields a wrong exit code"

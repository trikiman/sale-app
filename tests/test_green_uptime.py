"""v1.30 Phase 96 (GREEN-UP-03) — the uptime record behind the 168-hour proof.

The milestone goal is "no false green zero for a week". A spot check of
/api/products at a random moment cannot prove that; this suite pins the
recorder that can. All tests run without FastAPI or python-telegram-bot.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "backend"))


def _mod():
    import green_uptime as gu

    return gu


_MIN = 60.0
_HOUR = 3600.0


def _rec(gu, path, ts, ok=True, live=10, reason=None, exit_code=0, dur=120.0):
    gu.record_cycle(
        path, ts=ts, ok=ok, exit_code=exit_code, live_count=live,
        empty_reason=reason, duration_s=dur,
    )


# ── recording ───────────────────────────────────────────────────────────


def test_record_persists_one_jsonl_line(tmp_path) -> None:
    gu = _mod()
    p = str(tmp_path / "u.jsonl")
    _rec(gu, p, ts=1000.0, live=5)
    lines = Path(p).read_text().strip().split("\n")
    assert len(lines) == 1
    import json

    entry = json.loads(lines[0])
    assert entry["live_count"] == 5 and entry["ok"] is True


def test_record_never_raises_on_unwritable_path(tmp_path) -> None:
    gu = _mod()
    # a path whose parent is a *file* — directory creation must fail silently
    blocker = tmp_path / "blocker"
    blocker.write_text("x")
    gu.record_cycle(
        str(blocker / "sub" / "u.jsonl"),
        ts=1.0, ok=True, exit_code=0, live_count=0, empty_reason=None, duration_s=1,
    )
    assert True  # reaching here is the test


def test_summarize_no_data(tmp_path) -> None:
    gu = _mod()
    out = gu.summarize(str(tmp_path / "missing.jsonl"), now=10_000.0)
    assert out["verdict"] == "no_data" and out["cycles"] == 0


# ── verdicts ────────────────────────────────────────────────────────────


def test_healthy_week(tmp_path) -> None:
    gu = _mod()
    p = str(tmp_path / "u.jsonl")
    now = 10_000_000.0
    # one cycle per minute for 168 h — no gap ever exceeds 45 minutes
    t = now - 168 * _HOUR
    while t < now:
        _rec(gu, p, ts=t, live=12)
        t += 60.0
    out = gu.summarize(p, now=now)
    assert out["verdict"] == "healthy"
    assert out["gap_incident_count"] == 0
    assert out["false_zero_count"] == 0
    assert out["uptime_pct"] == 100.0
    assert out["hours_recorded"] >= 167


def test_gap_over_45_minutes_is_an_incident(tmp_path) -> None:
    gu = _mod()
    p = str(tmp_path / "u.jsonl")
    now = 10_000_000.0
    t = now - 48 * _HOUR
    while t < now - 5 * _HOUR:  # dense history, then dead air
        _rec(gu, p, ts=t, live=8)
        t += 60.0
    _rec(gu, p, ts=now - 1 * _HOUR)  # 4-hour gap before the last success
    out = gu.summarize(p, now=now)
    assert out["verdict"] == "incident"
    # the 4-hour hole plus the trailing hour both exceed 45 minutes
    assert out["gap_incident_count"] >= 1
    assert out["worst_gap_minutes"] >= 240


def test_short_history_is_insufficient_not_healthy(tmp_path) -> None:
    """A few clean hours must not report a healthy week — that would be a lie."""
    gu = _mod()
    p = str(tmp_path / "u.jsonl")
    now = 10_000_000.0
    for i in range(12):  # 12 minutes of history
        _rec(gu, p, ts=now - (12 - i) * 60.0)
    out = gu.summarize(p, now=now)
    assert out["verdict"] == "insufficient"


def test_trailing_dead_air_is_an_ongoing_incident(tmp_path) -> None:
    gu = _mod()
    p = str(tmp_path / "u.jsonl")
    now = 10_000_000.0
    t = now - 48 * _HOUR
    while t < now - 2 * _HOUR:
        _rec(gu, p, ts=t)
        t += 60.0
    # nothing for the last two hours
    out = gu.summarize(p, now=now)
    assert out["verdict"] == "incident"
    assert out["gap_incident_count"] == 1
    assert out["gap_incidents"][-1]["to_ts"] is None  # ongoing
    assert out["last_ok_age_minutes"] > 120


def test_false_zero_is_counted(tmp_path) -> None:
    """ok=True, zero products, no legit reason — exactly the v1.30 killer."""
    gu = _mod()
    p = str(tmp_path / "u.jsonl")
    now = 10_000_000.0
    t = now - 48 * _HOUR
    while t < now:
        _rec(gu, p, ts=t, live=0, reason=None)  # silent zero!
        t += 60.0
    out = gu.summarize(p, now=now)
    assert out["verdict"] == "incident"
    assert out["false_zero_count"] == len(Path(p).read_text().strip().split("\n"))


def test_source_empty_is_not_an_incident(tmp_path) -> None:
    """VkusVill itself having no green offers is a legitimate empty store."""
    gu = _mod()
    p = str(tmp_path / "u.jsonl")
    now = 10_000_000.0
    t = now - 48 * _HOUR
    while t < now:
        _rec(gu, p, ts=t, live=0, reason="source_empty")
        t += 60.0
    out = gu.summarize(p, now=now)
    assert out["false_zero_count"] == 0
    assert out["legit_empty_cycles"] > 0
    assert out["verdict"] == "healthy"


def test_failed_cycles_reduce_uptime(tmp_path) -> None:
    gu = _mod()
    p = str(tmp_path / "u.jsonl")
    now = 10_000_000.0
    t = now - 48 * _HOUR
    n = 0
    while t < now:
        _rec(gu, p, ts=t, ok=(n % 4 != 0), live=3, exit_code=0 if n % 4 != 0 else 1)
        t += 60.0
        n += 1
    out = gu.summarize(p, now=now)
    assert out["cycles_failed"] > 0
    assert out["uptime_pct"] < 100.0


def test_torn_line_does_not_kill_the_report(tmp_path) -> None:
    gu = _mod()
    p = str(tmp_path / "u.jsonl")
    now = 10_000_000.0
    t = now - 48 * _HOUR
    while t < now:
        _rec(gu, p, ts=t)
        t += 60.0
    with open(p, "a", encoding="utf-8") as f:
        f.write('{"ts": 1, "ok": tru')  # torn line, no newline at end
    out = gu.summarize(p, now=now)
    assert out["verdict"] in ("healthy", "insufficient")


# ── wiring ──────────────────────────────────────────────────────────────


def test_backend_exposes_the_uptime_endpoint() -> None:
    source = (_REPO_ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    assert "green_uptime" in source, "main.py never touches the uptime recorder"
    assert "/api/admin/green-uptime" in source, "the report endpoint is gone"
    assert "record_cycle(" in source, "cycles are no longer recorded"


def test_scheduler_parent_records_the_cycle() -> None:
    """Recording belongs to the parent — the child gets SIGKILLed.

    The watchdog (`proc.kill()`) and kill-triggers terminate scrape_green.py
    without unwinding, so its own `finally` never runs. Measured 2026-11-16: the
    soak read `cycles: 1` after an hour of real traffic because every cycle
    ended in a kill. The parent survives and knows the outcome.
    """
    source = (_REPO_ROOT / "scheduler_service.py").read_text(encoding="utf-8")
    assert "def _record_green_uptime(" in source, "parent-side recorder missing"
    assert 'if tag == "GREEN":' in source, "recording no longer gated on the green tag"
    idx = source.find('if tag == "GREEN":')
    window = source[idx : idx + 400]
    assert "killed_by_trigger" in window and "timed_out" in window, (
        "killed/timed-out runs must still be recorded as failures"
    )
    assert "green_products.json" in source


def test_scraper_does_not_record_a_second_time() -> None:
    src = (_REPO_ROOT / "scrape_green.py").read_text(encoding="utf-8")
    assert "_record_uptime" not in src, "child still records — double counting"
    assert "record_cycle(" not in src


def test_backend_does_not_double_count_manual_runs() -> None:
    source = (_REPO_ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    assert source.count("_uptime_record_outcome(\n") == 0, (
        "backend still records cycles — a manual run would be counted twice"
    )
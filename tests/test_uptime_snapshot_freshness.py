"""The soak recorder must not report a previous cycle's number as this cycle's result.

Observed 20.11.2026: `ok=False, exit_code=1, live_count=24` appeared repeatedly. A green run
that finds nothing leaves `green_products.json` untouched by design, so the recorder was
reading the PREVIOUS cycle's snapshot and pairing 24 greens with a failed run. The uptime log
must stay falsifiable: a failed cycle either shows its own count or shows nothing.
"""
import json
import os
import pathlib
import sys
import time

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from green_uptime import read_snapshot_fresh  # noqa: E402


@pytest.fixture()
def snapshot(tmp_path):
    path = tmp_path / "green_products.json"
    path.write_text(json.dumps({"live_count": 24, "empty_reason": "ok"}), encoding="utf-8")
    return path


def test_fresh_snapshot_is_read(snapshot):
    live, reason = read_snapshot_fresh(str(snapshot), cycle_started_ts=time.time() - 60)
    assert live == 24
    assert reason == "ok"


def test_snapshot_older_than_the_cycle_is_refused(snapshot):
    """The bug: an untouched file from a previous cycle must not be reported as a result."""
    old = time.time() - 3600
    os.utime(snapshot, (old, old))
    live, reason = read_snapshot_fresh(str(snapshot), cycle_started_ts=time.time() - 120)
    assert live is None, "a stale snapshot must not contribute a live_count"
    assert reason == "stale_snapshot_not_read"


def test_missing_snapshot_is_silent(tmp_path):
    live, reason = read_snapshot_fresh(str(tmp_path / "nope.json"), cycle_started_ts=time.time())
    assert (live, reason) == (None, None)


def test_broken_json_is_reported_not_raised(snapshot):
    snapshot.write_text("{not json", encoding="utf-8")
    live, reason = read_snapshot_fresh(str(snapshot), cycle_started_ts=time.time() - 10)
    assert live is None
    assert reason == "unreadable_snapshot"
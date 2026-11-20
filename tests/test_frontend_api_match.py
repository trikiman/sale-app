"""Contracts for scripts/check_frontend_matches_api.py.

The checker exists because a stale frontend and broken data look identical, and because I
personally reported a "6094 min old" frontend that was just my own cached tab. These tests
pin the two things that made it wrong: tier counting and the updatedAt timezone.
"""
import importlib.util
import pathlib
from datetime import datetime, timedelta, timezone

SPEC = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "check_frontend_matches_api.py"


def _mod():
    spec = importlib.util.spec_from_file_location("front_api_check", SPEC)
    assert spec is not None, f"cannot build a spec for {SPEC}"
    assert spec.loader is not None, f"no loader for {SPEC}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_tier_counts_only_known_types():
    m = _mod()
    payload = {"products": [{"type": "green"}, {"type": "red"}, {"type": "red"}, {}]}
    counts = m.tier_counts(payload)
    assert counts["green"] == 1
    assert counts["red"] == 2
    assert counts["yellow"] == 0


def test_updated_at_is_parsed_as_moscow_time():
    m = _mod()
    parsed = m.parse_updated("2026-11-20 23:10:30")
    assert parsed is not None
    assert parsed.utcoffset() == timedelta(hours=3)
    # 23:10 MSK is 20:10 UTC — the bug was treating it as UTC and reporting a future time
    assert parsed.astimezone(timezone.utc).hour == 20


def test_updated_at_tolerates_iso_separator_and_garbage():
    m = _mod()
    assert m.parse_updated("2026-11-20T23:10:30") is not None
    assert m.parse_updated("") is None
    assert m.parse_updated(None) is None
    assert m.parse_updated("not a date") is None
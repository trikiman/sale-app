"""A short-but-real scrape must not be reported as a failed cycle.

On 2026-11-27 the 12:15, 12:20 and 16:24 MSK runs each scraped 28/28/34 live
items and still exited 1: the >10 % shortfall against the badge count fell into
the branch that keeps the old snapshot and unconditionally failed the run. The
site was being served correctly the whole time, so those cycles only deflated
`uptime_pct` — one of the numbers the v1.30 soak report is about.

The split under test: keep the snapshot whenever the new list is shorter, but
count the cycle as FAILED only when the run scraped nearly nothing or the
snapshot it would preserve is itself stale.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

if "nodriver" not in sys.modules:  # scrape_green imports it at module load; absent on the workstation
    _stub = types.ModuleType("nodriver")
    _stub.cdp = types.SimpleNamespace()
    sys.modules["nodriver"] = _stub

from scrape_green import (  # noqa: E402
    GREEN_MISMATCH_MAX_SNAPSHOT_AGE_S,
    GREEN_MISMATCH_MIN_ITEMS,
    classify_green_count_mismatch,
)


def test_complete_list_is_saved():
    assert classify_green_count_mismatch(28, 28, 31, 300) == "save_new"
    assert classify_green_count_mismatch(31, 28, 31, 300) == "save_new"


def test_small_shortfall_inside_tolerance_is_saved():
    # 10 % of 40 live = 4, so 37 is inside tolerance
    assert classify_green_count_mismatch(37, 40, 50, 300) == "save_new"


def test_fresh_snapshot_with_meaningful_shortfall_keeps_ok():
    # exactly what happened live: 25 of 28 scraped, snapshot seconds old
    assert classify_green_count_mismatch(25, 28, 31, 120) == "preserve_ok"


def test_stale_snapshot_is_not_a_success():
    age = GREEN_MISMATCH_MAX_SNAPSHOT_AGE_S + 1
    assert classify_green_count_mismatch(25, 28, 31, age) == "preserve_fail"


def test_missing_snapshot_age_is_not_a_success():
    assert classify_green_count_mismatch(25, 28, 31, None) == "preserve_fail"


def test_nearly_nothing_scraped_is_not_a_success():
    below = GREEN_MISMATCH_MIN_ITEMS - 1
    assert classify_green_count_mismatch(below, 40, 60, 60) == "preserve_fail"


def test_bigger_new_list_is_saved_even_on_shortfall():
    # nothing better on disk than what we just scraped — write it
    assert classify_green_count_mismatch(20, 28, 18, 60) == "save_new"


def test_zero_and_junk_inputs_are_failures_not_successes():
    assert classify_green_count_mismatch(0, 28, 31, 10) == "save_new"
    assert classify_green_count_mismatch(20, 0, 0, 10) == "save_new"
    assert classify_green_count_mismatch("junk", 28, 31, 10) == "preserve_fail"

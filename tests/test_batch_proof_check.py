from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.batch_proof_check import summarize  # noqa: E402

LOG = [
    "[GREEN]   [GREEN] Green cards rendered: 40 (after 1.2s)",
    "[GREEN]   [GREEN] Batch 0-10: added 10 (running total 10)",
    "[GREEN]   [GREEN] Batch 10-20: added 10 (running total 20)",
    "[GREEN]   [GREEN] Added 20/40 items to cart",
    "[GREEN] nothing relevant here",
]


def test_two_ranges_in_one_window_is_the_proof():
    s = summarize(LOG)
    assert s["ranges"] == ["0-10", "10-20"]
    assert s["distinct_ranges"] == 2
    assert s["added_lines"] == ["[GREEN]   [GREEN] Added 20/40 items to cart"]


def test_single_range_does_not_count():
    s = summarize(["[GREEN] Batch 0-1: added 1 (running total 1)"])
    assert s["distinct_ranges"] == 1


def test_repeated_range_counts_once():
    s = summarize(["[GREEN] Batch 0-10: added 10", "[GREEN] Batch 0-10: added 10"])
    assert s["ranges"] == ["0-10"]
    assert s["hits"] == 2


def test_no_green_lines_is_zero_not_an_error():
    s = summarize(["[GREEN] nothing relevant", "plain line"])
    assert s["hits"] == 0 and s["distinct_ranges"] == 0 and s["ranges"] == []
"""A long yellow crawl must not look like a dead scraper.

Measured 2026-11-20 05:36 MSK: `yellow_products.json` was 32 minutes old while its
crawl was still running (48 -> 72 -> 96 -> 144 items, each page a DOM read). With a
30-minute threshold the API marked yellow stale and dropped all 122 yellow cards, so
the site showed **43 products instead of 165** even though no data was lost.

45 minutes matches green's budget: long enough for one paginated pass, short enough
to still catch a scraper that really died.
"""
from __future__ import annotations

import re


def _dict_block() -> str:
    src = open("backend/main.py", encoding="utf-8").read()
    start = src.index("DEFAULT_STALE_THRESHOLDS_MINUTES")
    return src[start:src.index("}", start)]


def test_yellow_threshold_is_45() -> None:
    block = _dict_block()
    assert re.search(r'"yellow":\s*45', block), "yellow must tolerate a long crawl"


def test_no_duplicate_keys_in_thresholds() -> None:
    block = _dict_block()
    keys = re.findall(r'"([a-z]+)":\s*\d+', block)
    assert len(keys) == len(set(keys)), f"duplicate keys shadow each other: {keys}"


def test_green_and_red_unchanged() -> None:
    block = _dict_block()
    assert re.search(r'"green":\s*45', block)
    # red moved 30 -> 45 on 2026-11-21: the cycle runs GREEN first and a big markdown day
    # (48 -> 96 modal cards, 69 products) pushed it past 30 minutes, so the API dropped all
    # 57 red cards while red_products.json was intact. A slow cycle is not staleness.
    assert re.search(r'"red":\s*45', block)

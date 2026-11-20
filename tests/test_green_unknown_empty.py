"""An empty green list is only success when VkusVill proves it is empty.

History: on 2026-11-20 05:12:12 UTC a run exited 0 with live_count 0 and
empty_reason=unknown_empty. The page was empty but no "Зелёных ценников сейчас нет"
banner was rendered, so nothing proved the emptiness — yet the run claimed success and
the soak recorded a false zero. `green_empty.classify_empty_state()` now decides both
the reason and whether the emptiness is proven; unproven emptiness must fail the run.

The module is imported directly (not scrape_green) so the test needs no nodriver/CDP.
"""
from __future__ import annotations

import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from green_empty import classify_empty_state  # noqa: E402


def test_products_present_is_ok() -> None:
    assert classify_empty_state([{"id": 1}], False) == ("ok", True)


def test_banner_makes_empty_source_empty_and_proven() -> None:
    assert classify_empty_state([], True) == ("source_empty", True)


def test_empty_without_banner_is_unknown_and_unproven() -> None:
    reason, proven = classify_empty_state([], False)
    assert reason == "unknown_empty"
    assert proven is False, "unproven emptiness must never be reported as success"


def test_banner_does_not_rescue_a_non_empty_list() -> None:
    assert classify_empty_state([{"id": 2}], True) == ("ok", True)


def test_scrape_green_uses_the_shared_classifier() -> None:
    """Guard against re-growing a second copy of the rule inside the scraper."""
    src = (ROOT / "scrape_green.py").read_text(encoding="utf-8")
    assert "from green_empty import classify_empty_state" in src
    assert "def classify_empty_state" not in src

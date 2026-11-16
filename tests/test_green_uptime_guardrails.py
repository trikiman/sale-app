"""v1.30 Phase 94 (GREEN-UP-01/04) — green visibility guardrails.

Pins the invariant that produced the recurring false "0 зелёных":

    the API returned an empty green list while green_products.json held real
    products, because `/api/products` stripped every stale colour and green was
    simply another colour.

Background (measured 2026-11-15): `greenLiveCount` was 6 and
`green_products.json` held 6 real products with real markdowns, while
`/api/products` carried none and `staleInfo` said `["green (16m)"]`.

These tests fail if anyone reinstates "staleness hides green".
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
# The policy module sits in backend/ and has no heavy imports, so we can load it
# without pulling FastAPI/nodriver/bot deps (which are absent in the test venv).
if str(_REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "backend"))


def _vis(**kwargs):
    from green_visibility import green_visibility

    return green_visibility(**kwargs)


# ── the hook itself ─────────────────────────────────────────────────────


def test_fresh_snapshot_with_products_is_visible() -> None:
    assert _vis(is_stale=False, has_snapshot_products=True, empty_reason=None) == (
        True,
        None,
    )


def test_stale_snapshot_with_products_stays_visible() -> None:
    """The regression that caused the false zero: stale must not hide green."""
    assert _vis(is_stale=True, has_snapshot_products=True, empty_reason=None) == (
        True,
        None,
    )


@pytest.mark.parametrize("reason", ["source_empty", "missing"])
def test_explicit_empty_signal_hides_green(reason: str) -> None:
    visible, why = _vis(is_stale=True, has_snapshot_products=False, empty_reason=reason)
    assert visible is False
    assert why == reason


def test_empty_snapshot_without_reason_hides_green() -> None:
    visible, why = _vis(is_stale=False, has_snapshot_products=False, empty_reason=None)
    assert visible is False
    assert why == "no_snapshot_products"


def test_unknown_empty_reason_with_products_is_still_visible() -> None:
    """A scraper miss may leave empty_reason unset or odd; products win."""
    visible, why = _vis(
        is_stale=True, has_snapshot_products=True, empty_reason="unknown_empty"
    )
    assert (visible, why) == (True, None)


def test_staleness_argument_cannot_hide_green_even_with_every_stale_flag() -> None:
    """Belt and suspenders: whatever stale flag is passed, products win."""
    for stale in (True, False):
        for reason in (None, "unknown_empty", "scraper_error"):
            visible, _ = _vis(
                is_stale=stale, has_snapshot_products=True, empty_reason=reason
            )
            assert visible is True, (stale, reason)


# ── the source must not regain the unconditional strip ──────────────────


def test_api_source_has_no_unconditional_green_strip() -> None:
    """Reads backend/main.py and refuses the old code shape.

    The old bug was:
        data["products"] = [p for p in data["products"] if p.get("type") not in stale_types]
    with no green exception, i.e. green vanished purely because it was stale.
    """
    source = (_REPO_ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    assert "green_visibility(" in source, "green visibility hook was removed"
    # the strip must consult the hook before dropping green
    strip_idx = source.find('if "green" in _strip:')
    assert strip_idx != -1, "green special-case in the stale strip was removed"
    window = source[strip_idx : strip_idx + 700]
    assert "green_visibility(" in window, "stale strip no longer asks green_visibility"
    assert "_strip.discard(\"green\")" in window, "green is not spared when visible"


def test_api_always_reports_suppression_reason() -> None:
    source = (_REPO_ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    assert '"greenSuppressed"' in source
    assert "payload_missing_but_snapshot_has_products" in source
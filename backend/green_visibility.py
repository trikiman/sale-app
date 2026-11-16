"""Green tag visibility policy (v1.30 GREEN-UP-01).

Single source of truth for one question: **may the API show green cards?**

Why this lives in its own module: it is the exact decision that produced the
recurring false "0 зелёных". `backend/main.py` used to strip every stale colour
including green, so a snapshot that our scraper had failed to refresh for 16
minutes looked identical to "VkusVill has no green offers" — while
`green_products.json` still held 6-77 products with real markdowns.

Keeping the rule dependency-free means it is testable without FastAPI, a
database, or a live server, and it cannot quietly grow a second implementation
inside the endpoint.

Rule: **staleness never hides green.** A stale snapshot means we missed
refresh cycles, not that the offers vanished. Only two things may hide it:
an empty snapshot, or VkusVill's own "no green tags" signal.
"""

from __future__ import annotations

# Reasons that legitimately leave green hidden. `source_empty` is VkusVill's own
# banner ("Зелёных ценников сейчас нет"); `missing` means there is no usable
# snapshot at all.
GREEN_HIDDEN_EMPTY_REASONS: tuple[str, ...] = ("source_empty", "missing")


def green_visibility(
    *,
    is_stale: bool,
    has_snapshot_products: bool,
    empty_reason: str | None,
) -> tuple[bool, str | None]:
    """Return ``(visible, suppressed_reason)``.

    ``is_stale`` is accepted so callers pass full context (and so tests can pin
    the invariant that staleness is NOT a hiding reason), but it deliberately
    does not influence the result.
    """
    del is_stale  # see docstring — never a hiding reason
    if empty_reason in GREEN_HIDDEN_EMPTY_REASONS:
        return False, str(empty_reason)
    if not has_snapshot_products:
        return False, "no_snapshot_products"
    return True, None
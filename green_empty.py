"""Why is the green list empty — and is that emptiness PROVEN?

Dependency-free on purpose: this is the one decision that produced the milestone's
false zero. On 2026-11-20 05:12:12 UTC a run exited 0 with live_count 0 and
empty_reason=unknown_empty: the page was empty, no "Зелёных ценников сейчас нет"
banner was rendered, so nothing proved the emptiness — and the run still claimed
success.

Rule: an empty list is success ONLY when VkusVill itself says so. Everything else is
unproven and must fail the run, keeping the previous snapshot untouched.
"""

from __future__ import annotations


def classify_empty_state(products, empty_explicit):
    """Return (empty_reason, is_proven).

    - products non-empty          -> ("ok", True)
    - empty + explicit banner     -> ("source_empty", True)
    - empty + no banner           -> ("unknown_empty", False)  # never a success
    """
    if products:
        return "ok", True
    if empty_explicit:
        return "source_empty", True
    return "unknown_empty", False

"""Bounded JSONL ledger for /api/product/{id}/details timing + outcomes.

Phase 74 (v1.23 PERF-11).

Schema — one line per /api/product/{id}/details call::

    {"ts": 1747123456.789, "product_id": "33215",
     "duration_ms": 1823, "cached": false,
     "retry_count": 1, "outcome": "ok"}

Outcomes:
    "cached"    — cache hit (retry_count=0, cached=true)
    "ok"        — 200 response, >500 bytes, parsed successfully
    "fallback"  — fetched but html too short / unreadable
    "failed"    — all retries exhausted with exception/non-200

Bounded via MAX_LINES prune matching the v1.20 cart_events pattern.
Callers must never crash the endpoint on ledger I/O errors — every
function in this module swallows its own exceptions and logs at debug.

The ledger path honors the ``SALEAPP_DETAIL_EVENTS_PATH`` env var so
tests can point it at a tmp directory; production uses the default
``<repo>/data/detail_events.jsonl``.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Literal

Outcome = Literal["cached", "ok", "fallback", "failed"]

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_PATH = os.path.join(_BASE_DIR, "data", "detail_events.jsonl")

# Read env override at import time; tests that need a per-test path
# monkeypatch ``LEDGER_PATH`` directly on this module instead.
LEDGER_PATH = os.environ.get("SALEAPP_DETAIL_EVENTS_PATH") or _DEFAULT_PATH

# Bound the ledger — keep ~1 MB at ~100-200 bytes/line.
MAX_LINES = 5000
PRUNE_KEEP = 4000

_logger = logging.getLogger(__name__)


def append_event(
    *,
    product_id: str,
    duration_ms: int,
    cached: bool,
    retry_count: int,
    outcome: Outcome,
) -> None:
    """Append one event line. Never raises."""
    entry = {
        "ts": round(time.time(), 3),
        "product_id": str(product_id),
        "duration_ms": int(duration_ms),
        "cached": bool(cached),
        "retry_count": int(retry_count),
        "outcome": outcome,
    }
    try:
        target = LEDGER_PATH
        parent = os.path.dirname(target)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(target, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, separators=(",", ":")) + "\n")
        _maybe_prune()
    except Exception:  # noqa: BLE001 - ledger must never crash the endpoint
        _logger.debug("detail_events append failed", exc_info=False)


def _maybe_prune() -> None:
    """Prune oldest lines when file exceeds MAX_LINES. Never raises."""
    try:
        target = LEDGER_PATH
        if not os.path.exists(target):
            return
        with open(target, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
        if len(lines) <= MAX_LINES:
            return
        keep = lines[-PRUNE_KEEP:]
        tmp = target + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.writelines(keep)
        os.replace(tmp, target)
    except Exception:  # noqa: BLE001
        _logger.debug("detail_events prune failed", exc_info=False)


def read_recent(limit: int = 100) -> list[dict]:
    """Tail the last ``limit`` events. Returns [] on any read failure."""
    try:
        target = LEDGER_PATH
        if not os.path.exists(target):
            return []
        with open(target, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
        out: list[dict] = []
        for line in lines[-limit:]:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out
    except Exception:  # noqa: BLE001
        return []

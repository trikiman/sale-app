"""Pre-flight probe for the local VLESS SOCKS5 bridge.

Checks that ``socks5h://127.0.0.1:10808`` can actually reach VkusVill before
the scheduler spends 30-45 seconds launching Chrome. Used by
``scheduler_service.py::_run_scraper_set``.

Design decisions (see
``.planning/phases/59-corrected-preflight-vless-probe/59-CONTEXT.md``):

- Target: ``https://vkusvill.ru/favicon.ico`` — same domain as real traffic,
  small (~5 KB), stable.
- Timeout: 12 s (empirical healthy p95 = 9.2 s × 1.3 safety margin). MUST
  stay >= 12 s; regression-tested by
  ``tests/test_preflight_timeout_regression.py``. Measured 2026-05-03 on EC2
  through the live bridge. If re-tuning, re-measure first.
- Cache: 30 s TTL on last success. Back-to-back scraper launches within the
  same cycle skip the probe (REL-05).
- Accepted statuses: {200, 204, 304, 403, 404} — 4xx from VkusVill's edge is
  still proof the bridge reaches VkusVill.
- Rotation: probe failure signals the caller to rotate; rotation itself is
  NOT done here (kept in scheduler_service for visibility).

Corrected successor to the reverted PR #25 (5 s timeout was below empirical
7-9 s healthy latency; 5 rotations cascaded 5 xray restarts per bad-probe
window). This module fixes both mistakes.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import httpx

_PROBE_URL = "https://vkusvill.ru/favicon.ico"
# DO NOT LOWER — see module docstring + tests/test_preflight_timeout_regression.py
_PROBE_TIMEOUT_S_FLOOR = 12.0
_CACHE_TTL_S = 30.0
_ACCEPTED_STATUSES = frozenset({200, 204, 304, 403, 404})
_BRIDGE_PROXY = "socks5h://127.0.0.1:10808"

# Module-level cache of last successful probe timestamp (monotonic seconds).
_LAST_SUCCESS_AT: Optional[float] = None


@dataclass(frozen=True)
class ProbeResult:
    """Outcome of a single pre-flight probe attempt."""

    ok: bool
    status: Optional[int]
    # One of: "ok" | "cached" | "timeout" | "connect_error" | "dns_fail" | f"http_{code}"
    reason: str
    elapsed_s: float
    cached: bool = False


def probe_bridge_alive(timeout: float = _PROBE_TIMEOUT_S_FLOOR) -> ProbeResult:
    """Single HTTPS GET to VkusVill through the local SOCKS5 bridge.

    Returns a typed :class:`ProbeResult`. Never raises. Caller uses
    ``.ok`` to decide whether to rotate + retry.

    If the last successful probe was within ``_CACHE_TTL_S`` (30 s), return
    a cached OK without hitting the network.

    :param timeout: HTTP timeout in seconds. Must be >=
        ``_PROBE_TIMEOUT_S_FLOOR``; the floor is enforced at runtime to
        prevent PR #25-style regression where 5 s false-negatived healthy
        nodes with ~9 s latency.
    """
    global _LAST_SUCCESS_AT

    effective_timeout = max(float(timeout), _PROBE_TIMEOUT_S_FLOOR)

    if _LAST_SUCCESS_AT is not None:
        age = time.monotonic() - _LAST_SUCCESS_AT
        if age <= _CACHE_TTL_S:
            return ProbeResult(
                ok=True, status=None, reason="cached", elapsed_s=0.0, cached=True
            )

    start = time.monotonic()
    try:
        with httpx.Client(
            proxy=_BRIDGE_PROXY,
            timeout=effective_timeout,
            verify=True,
            follow_redirects=False,
        ) as client:
            resp = client.get(_PROBE_URL)
        elapsed = time.monotonic() - start
        if resp.status_code in _ACCEPTED_STATUSES:
            _LAST_SUCCESS_AT = time.monotonic()
            return ProbeResult(
                ok=True, status=resp.status_code, reason="ok", elapsed_s=elapsed
            )
        _LAST_SUCCESS_AT = None
        return ProbeResult(
            ok=False,
            status=resp.status_code,
            reason=f"http_{resp.status_code}",
            elapsed_s=elapsed,
        )
    except httpx.ConnectTimeout:
        _LAST_SUCCESS_AT = None
        return ProbeResult(
            ok=False,
            status=None,
            reason="timeout",
            elapsed_s=time.monotonic() - start,
        )
    except httpx.ReadTimeout:
        _LAST_SUCCESS_AT = None
        return ProbeResult(
            ok=False,
            status=None,
            reason="timeout",
            elapsed_s=time.monotonic() - start,
        )
    except httpx.ConnectError as exc:
        _LAST_SUCCESS_AT = None
        reason = (
            "dns_fail"
            if "name or service" in str(exc).lower()
            else "connect_error"
        )
        return ProbeResult(
            ok=False,
            status=None,
            reason=reason,
            elapsed_s=time.monotonic() - start,
        )
    except httpx.HTTPError:
        _LAST_SUCCESS_AT = None
        return ProbeResult(
            ok=False,
            status=None,
            reason="connect_error",
            elapsed_s=time.monotonic() - start,
        )


def reset_probe_cache() -> None:
    """Clear the last-success cache. Used by tests; rarely by callers."""
    global _LAST_SUCCESS_AT
    _LAST_SUCCESS_AT = None


__all__ = ["ProbeResult", "probe_bridge_alive", "reset_probe_cache"]

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

# v1.30 GREEN-EGRESS-01: probe order, URnetwork first.
#
# `urn-ru-0` used to be merely one member of the leastPing balancer, so Xray
# could pick a dead VLESS node instead — and by 2026-11-16 the pool had decayed
# to one node and the scheduler logged "VkusVill: BLOCKED (direct connection
# failed)", stalling every green cycle. Port 10809 is pinned to URnetwork by an
# inbound+pinned-route pair in `config_gen.py`, so here we try it first and fall
# back to the general balancer on 10808 only when it fails.
_BRIDGE_PROXIES: tuple[tuple[str, str], ...] = (
    ("urnetwork", "socks5h://127.0.0.1:10809"),
    ("vless", "socks5h://127.0.0.1:10808"),
)
_BRIDGE_PROXY = _BRIDGE_PROXIES[-1][1]  # kept for backwards compatibility

# Module-level cache of last successful probe timestamp (monotonic seconds),
# per route: a healthy URnetwork must not mask a dead VLESS balancer.
_LAST_SUCCESS_AT: dict[str, float] = {}


@dataclass(frozen=True)
class ProbeResult:
    """Outcome of a single pre-flight probe attempt."""

    ok: bool
    status: Optional[int]
    # One of: "ok" | "cached" | "timeout" | "connect_error" | "dns_fail" | f"http_{code}"
    reason: str
    elapsed_s: float
    cached: bool = False
    # "urnetwork" | "vless" — which egress actually served the probe.
    route: str = ""


def _probe_once(proxy: str, effective_timeout: float, route: str) -> ProbeResult:
    """Single probe attempt through one SOCKS bridge. Never raises."""
    start = time.monotonic()
    try:
        with httpx.Client(
            proxy=proxy,
            timeout=effective_timeout,
            verify=True,
            follow_redirects=False,
        ) as client:
            resp = client.get(_PROBE_URL)
        elapsed = time.monotonic() - start
        if resp.status_code in _ACCEPTED_STATUSES:
            return ProbeResult(
                ok=True, status=resp.status_code, reason="ok",
                elapsed_s=elapsed, route=route,
            )
        return ProbeResult(
            ok=False, status=resp.status_code,
            reason=f"http_{resp.status_code}", elapsed_s=elapsed, route=route,
        )
    except (httpx.ConnectTimeout, httpx.ReadTimeout):
        return ProbeResult(
            ok=False, status=None, reason="timeout",
            elapsed_s=time.monotonic() - start, route=route,
        )
    except httpx.ConnectError as exc:
        return ProbeResult(
            ok=False, status=None,
            reason=("dns_fail" if "name or service" in str(exc).lower() else "connect_error"),
            elapsed_s=time.monotonic() - start, route=route,
        )
    except httpx.HTTPError:
        return ProbeResult(
            ok=False, status=None, reason="connect_error",
            elapsed_s=time.monotonic() - start, route=route,
        )


def probe_bridge_alive(timeout: float = _PROBE_TIMEOUT_S_FLOOR) -> ProbeResult:
    """Probe VkusVill through the local SOCKS bridges, URnetwork first.

    Returns a typed :class:`ProbeResult` whose ``route`` names the egress that
    answered (``"urnetwork"`` on :10809, ``"vless"`` on :10808). Callers must
    launch Chrome against the port of the winning route, otherwise the probe
    would vouch for a channel the browser never uses.

    A per-route 30 s cache short-circuits repeated probes; a healthy URnetwork
    never masks a dead balancer because the cache is keyed by route.

    :param timeout: HTTP timeout in seconds, floored at
        ``_PROBE_TIMEOUT_S_FLOOR`` to keep PR #25 from returning.
    """
    effective_timeout = max(float(timeout), _PROBE_TIMEOUT_S_FLOOR)

    for route, proxy in _BRIDGE_PROXIES:
        last = _LAST_SUCCESS_AT.get(route)
        if last is not None and (time.monotonic() - last) <= _CACHE_TTL_S:
            return ProbeResult(
                ok=True, status=None, reason="cached", elapsed_s=0.0,
                cached=True, route=route,
            )

        result = _probe_once(proxy, effective_timeout, route)
        if result.ok:
            _LAST_SUCCESS_AT[route] = time.monotonic()
            return result
        _LAST_SUCCESS_AT.pop(route, None)

    # Every route failed: report the first (primary) route's failure so the log
    # names the channel we actually prefer, not the fallback's error.
    return _probe_once(_BRIDGE_PROXIES[0][1], effective_timeout, _BRIDGE_PROXIES[0][0])


def reset_probe_cache() -> None:
    """Clear the last-success cache. Used by tests; rarely by callers."""
    _LAST_SUCCESS_AT.clear()


__all__ = ["ProbeResult", "probe_bridge_alive", "reset_probe_cache"]

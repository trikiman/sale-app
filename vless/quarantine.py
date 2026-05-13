"""Persistent probe-failure quarantine for VLESS nodes.

Phase 77 (v1.24 REL-16). Complements the existing ``vkusvill_cooldown``
(which tracks "VkusVill blocked this host at layer-7") with a separate
quarantine for nodes that failed the TCP/xray probe itself — i.e., nodes
where the VLESS bridge couldn't even connect.

Why we need this:
    Before v1.24, every ``refresh_proxy_list`` call re-probed the same
    ~231 RU-filtered nodes from scratch. Dead nodes from 2 min ago got
    re-tested. During the 2026-05-13 outage this produced 19 refreshes
    in 15 min with identical ``Parsed 519 nodes / Geo-filter: 231 RU``
    telemetry every time — pure wasted work that slowed pool recovery
    from the target ~10 min to the observed ~1 hour.

Behavior:
    - A host is quarantined after failing its probe.
    - Default TTL: 20 min (``QUARANTINE_TTL_S``).
    - Hosts with ``fail_count >= 3`` get the 4h TTL (repeat offender —
      same duration as the existing ``VKUSVILL_COOLDOWN_S`` for layer-7
      blocks).
    - Expired entries are pruned on every read.
    - JSON store at ``<repo>/data/pool_quarantine.json``, schema::

        {
          "quarantined": {
            "<host>:<port>": {
              "reason": str,               # "probe_timeout" | "probe_error"
              "first_failed_at": float,    # unix ts
              "last_failed_at": float,
              "fail_count": int,
              "expires_at": float,
            },
            ...
          }
        }

Callers must never crash on quarantine I/O errors. Every public function
swallows exceptions and logs at debug.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Iterable

_logger = logging.getLogger(__name__)

# Default quarantine TTL (seconds). Match the scheduler cycle cadence so
# 60-min+ outages clear through the deadlist naturally.
#
# v1.26 Phase 84.1: graduated TTL by failure reason + strike count.
# Before: every probe failure = 20 min lockout. Effect: a single ipinfo.io
# rate-limit or transient TCP blip put healthy nodes into a 20-min
# deadlist, and on EC2 we observed 120/141 RU candidates quarantined
# from a single bad cycle — the entire pool starved itself.
#
# After:
#   - SOFT_TTL (60s)            — first-strike for transient reasons
#                                  (probe_timeout, probe_error, xray_start_error,
#                                  egress_unknown). Self-heals fast.
#   - QUARANTINE_TTL_S (20 min) — second strike on transient reasons OR
#                                  first strike on hard-block reasons
#                                  (vpn_detected — VkusVill served the
#                                  geo-block landing page).
#   - REPEAT_OFFENDER_TTL_S (4h) — fail_count >= 3 within last hour.
SOFT_TTL_S = 60                      # 1 minute — recover-fast tier
QUARANTINE_TTL_S = 20 * 60           # 20 minutes — confirmed-bad tier
REPEAT_OFFENDER_TTL_S = 4 * 60 * 60  # 4 hours — repeat offender
REPEAT_OFFENDER_THRESHOLD = 3        # fail_count >= this → use longer TTL

# Reasons that justify skipping the soft-tier and going straight to the
# 20-min lockout. These represent "VkusVill explicitly rejected this exit"
# rather than "we couldn't probe it cleanly." Anything not in this set
# enters at SOFT_TTL on first strike.
HARD_REASONS = frozenset({
    "vpn_detected",          # VkusVill served /vpn-detected/ landing
    "egress_country_non_ru", # confirmed non-RU egress
    "tls_handshake_failed",  # cert mismatch on Reality SNI — server-side fault
})

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_PATH = os.path.join(_BASE_DIR, "data", "pool_quarantine.json")

# Test hooks honor this env var override.
QUARANTINE_PATH = os.environ.get("SALEAPP_POOL_QUARANTINE_PATH") or _DEFAULT_PATH


def _load_raw() -> dict:
    """Load quarantine file. Returns empty skeleton on any error."""
    try:
        with open(QUARANTINE_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            return {"quarantined": {}}
        if "quarantined" not in data or not isinstance(data["quarantined"], dict):
            data["quarantined"] = {}
        return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {"quarantined": {}}
    except Exception:  # noqa: BLE001
        _logger.debug("quarantine load failed", exc_info=False)
        return {"quarantined": {}}


def _save_raw(data: dict) -> None:
    """Persist quarantine file atomically. Never raises."""
    try:
        parent = os.path.dirname(QUARANTINE_PATH)
        if parent:
            os.makedirs(parent, exist_ok=True)
        tmp = QUARANTINE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, separators=(",", ":"), ensure_ascii=False)
        os.replace(tmp, QUARANTINE_PATH)
    except Exception:  # noqa: BLE001
        _logger.debug("quarantine save failed", exc_info=False)


def _prune_expired(data: dict, now: float | None = None) -> dict:
    """Remove entries whose expires_at <= now. Returns the same dict."""
    now = now if now is not None else time.time()
    entries = data.get("quarantined", {})
    alive = {
        host: entry
        for host, entry in entries.items()
        if isinstance(entry, dict) and entry.get("expires_at", 0) > now
    }
    data["quarantined"] = alive
    return data


def get_quarantined_hosts() -> set[str]:
    """Return the set of currently-quarantined ``host:port`` strings."""
    data = _prune_expired(_load_raw())
    # Only write back if pruning actually changed something (avoid
    # touching the file on every read).
    return set(data.get("quarantined", {}).keys())


def is_quarantined(host_port: str) -> bool:
    """True if ``host_port`` is currently quarantined."""
    return host_port in get_quarantined_hosts()


def _compute_ttl(fail_count: int, reason: str) -> int:
    """v1.26 Phase 84.1: graduated TTL by strike count + reason.

    Logic:
      - fail_count >= REPEAT_OFFENDER_THRESHOLD (3+) → 4h hard lockout.
      - reason in HARD_REASONS → straight to 20 min on first strike.
      - First-strike on a transient reason → 60s soft cooldown.
      - Second-strike on a transient reason → 20 min lockout.

    The soft-cooldown tier is the key fix: a single ipinfo.io rate-limit
    or one TCP timeout no longer deadlists a healthy node for 20 min.
    """
    if fail_count >= REPEAT_OFFENDER_THRESHOLD:
        return REPEAT_OFFENDER_TTL_S
    if reason in HARD_REASONS:
        return QUARANTINE_TTL_S
    if fail_count <= 1:
        return SOFT_TTL_S
    return QUARANTINE_TTL_S


def record_probe_failure(host_port: str, reason: str = "probe_error") -> None:
    """Record a probe failure for ``host_port``.

    TTL ladder (see :func:`_compute_ttl`):
      - 1 strike, transient reason: 60s
      - 1 strike, hard reason: 20 min
      - 2 strikes, transient reason: 20 min
      - 3+ strikes: 4h
    """
    try:
        now = time.time()
        data = _prune_expired(_load_raw(), now=now)
        entries = data["quarantined"]

        existing = entries.get(host_port)
        if existing and isinstance(existing, dict):
            fail_count = int(existing.get("fail_count", 0)) + 1
            first_failed_at = float(existing.get("first_failed_at", now))
        else:
            fail_count = 1
            first_failed_at = now

        ttl = _compute_ttl(fail_count, reason)
        entries[host_port] = {
            "reason": str(reason),
            "first_failed_at": first_failed_at,
            "last_failed_at": now,
            "fail_count": fail_count,
            "expires_at": now + ttl,
            "ttl_s": ttl,  # surface in admin snapshots / debug logs
        }
        _save_raw(data)
    except Exception:  # noqa: BLE001
        _logger.debug("quarantine record failed", exc_info=False)


def record_probe_failures(host_ports: Iterable[str], reason: str = "probe_error") -> None:
    """Batch-record multiple failures (saves a single write instead of N)."""
    try:
        now = time.time()
        data = _prune_expired(_load_raw(), now=now)
        entries = data["quarantined"]

        for host_port in host_ports:
            existing = entries.get(host_port)
            if existing and isinstance(existing, dict):
                fail_count = int(existing.get("fail_count", 0)) + 1
                first_failed_at = float(existing.get("first_failed_at", now))
            else:
                fail_count = 1
                first_failed_at = now

            ttl = _compute_ttl(fail_count, reason)
            entries[host_port] = {
                "reason": str(reason),
                "first_failed_at": first_failed_at,
                "last_failed_at": now,
                "fail_count": fail_count,
                "expires_at": now + ttl,
                "ttl_s": ttl,
            }
        _save_raw(data)
    except Exception:  # noqa: BLE001
        _logger.debug("quarantine batch record failed", exc_info=False)


def release(host_port: str) -> None:
    """Remove a host from quarantine (e.g., after successful probe)."""
    try:
        data = _load_raw()
        if host_port in data.get("quarantined", {}):
            del data["quarantined"][host_port]
            _save_raw(data)
    except Exception:  # noqa: BLE001
        _logger.debug("quarantine release failed", exc_info=False)


def release_soft_quarantined() -> set[str]:
    """v1.26 Phase 84.1: release entries that are in the soft-cooldown tier.

    Used by the candidate-exhaustion recovery path in
    :meth:`VlessProxyManager.refresh_proxy_list`. Releases only entries
    whose ``ttl_s`` is the SOFT_TTL_S tier (60s) — these are first-strike
    transient failures that we want to retry immediately when the funnel
    has nothing else. Hard-tier (20-min vpn_detected, geo-block) and
    4h repeat-offender entries are NEVER released by this helper because
    those represent confirmed-bad nodes.

    Returns the set of released host:port strings (for logging).
    """
    try:
        data = _load_raw()
        entries = data.get("quarantined", {})
        released: set[str] = set()
        for host_port, entry in list(entries.items()):
            if not isinstance(entry, dict):
                continue
            # Use ttl_s if present (new schema), fall back to inferring
            # from expires_at - last_failed_at for legacy entries.
            ttl_s = entry.get("ttl_s")
            if ttl_s is None:
                expires = float(entry.get("expires_at", 0))
                last = float(entry.get("last_failed_at", 0))
                ttl_s = max(0, expires - last)
            if ttl_s <= SOFT_TTL_S:
                del entries[host_port]
                released.add(host_port)
        if released:
            data["quarantined"] = entries
            _save_raw(data)
        return released
    except Exception:  # noqa: BLE001
        _logger.debug("quarantine soft-release failed", exc_info=False)
        return set()


def clear_all() -> None:
    """Wipe the quarantine (ops tool; used by smoke scripts)."""
    try:
        _save_raw({"quarantined": {}})
    except Exception:  # noqa: BLE001
        _logger.debug("quarantine clear failed", exc_info=False)


def snapshot() -> dict:
    """Return the full quarantine state (for debugging / health endpoints)."""
    data = _prune_expired(_load_raw())
    return {
        "count": len(data.get("quarantined", {})),
        "hosts": sorted(data.get("quarantined", {}).keys()),
        "entries": data.get("quarantined", {}),
    }

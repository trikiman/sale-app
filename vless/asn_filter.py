"""ASN-based pre-filter for VLESS candidates.

Why this exists
---------------
VkusVill does not accept traffic from most datacenter ASNs. Measured
2026-11-13 via Globalping with real probes (HTTPS HEAD ``/``):

===========  ==================  ==================
ASN          Provider            Reachability
===========  ==================  ==================
AS9123       Timeweb             5/5   (100%)
AS50340      Selectel            3/4   (75%)
AS200350     Yandex.Cloud        0/4   (0%)
===========  ==================  ==================

Our own Oracle Amsterdam box is blocked outright (all 4 NL probes
timed out). This is *not* an RKN block: VkusVill is on the official
whitelist, and a Russian residential IP reaches it in 0.55 s. It is
per-ASN filtering on VkusVill's edge (they even host a
``/vpn-detected/`` landing page and their support page warns that VPNs
break checkout).

Consequence for the pool: candidates from blocked ASNs can never be
admitted. Today they are still put through the full three-stage probe
(TCP open → xray subprocess → ``_probe_vkusvill`` + egress geo), which
costs roughly 6 s each. Free aggregator feeds routinely contain 20+
Yandex.Cloud nodes per refresh, so ~2 minutes of the refresh budget is
spent proving something we already know.

This module rejects them up front for ~1 HTTP request per 100 hosts.

Design constraints
------------------
- **Fail open.** Any network/parse error returns the input unchanged.
  A broken geolocation lookup must never empty the pool.
- **Only IPv4 literals.** Hostnames are passed through untouched — we
  cannot resolve them cheaply and must not guess.
- **Cached on disk** (7-day TTL). ASN ownership is stable; re-querying
  every refresh would waste the free tier's 45 req/min budget.
- **Small blocklist.** Only ASNs with measured 0% reachability. Do not
  add "suspicious" ASNs here — an over-eager blocklist is worse than a
  slow refresh.
"""
from __future__ import annotations

import ipaddress
import json
import logging
import time
from pathlib import Path
from typing import Any, Iterable

from vless.parser import VlessNode

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------- policy ----

#: ASNs measured to have 0% VkusVill reachability. Keep this list tiny and
#: evidence-based — every entry here permanently removes nodes from the pool.
#: Evidence: .planning/research/vkusvill-access-rkn-check.md (2026-11-13).
BLOCKED_ASNS: frozenset[int] = frozenset({
    200350,  # Yandex.Cloud               — 0/4 probes reached vkusvill.ru
    207713,  # Global Internet Solutions   — 0/3 probes (Novosibirsk)
    47764,   # VK                          — 0/1 probe (Moscow)
})

#: Opt-in allowlist priority hint. Not enforced: these ASNs are simply
#: attempted first so the refresh deadline is spent on nodes that can pass.
PREFERRED_ASNS: frozenset[int] = frozenset({
    9123,   # Timeweb — 5/5 reachable
    50340,  # Selectel MSK — 3/4 reachable
    49505,  # Selectel SPb — mixed but never blocked at TCP layer
})

_CACHE_TTL_S = 7 * 24 * 3600
_BATCH_URL = "http://ip-api.com/batch?fields=query,status,as,asname,countryCode"
_BATCH_SIZE = 100
_MAX_BATCHES = 5          # hard cap: 500 hosts per refresh, protects the budget
_HTTP_TIMEOUT_S = 8.0


def _cache_path() -> Path:
    root = Path(__file__).resolve().parent.parent
    return root / ".cache" / "asn_lookup.json"


def _load_cache() -> dict[str, dict[str, Any]]:
    path = _cache_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    now = time.time()
    return {
        ip: entry
        for ip, entry in raw.items()
        if isinstance(entry, dict) and now - float(entry.get("ts", 0)) < _CACHE_TTL_S
    }


def _save_cache(cache: dict[str, dict[str, Any]]) -> None:
    path = _cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass  # cache is an optimisation; losing it is harmless


def _is_ipv4_literal(host: str) -> bool:
    try:
        ipaddress.IPv4Address(host)
        return True
    except ValueError:
        return False


def _lookup_uncached(ips: list[str]) -> dict[str, dict[str, Any]]:
    """Batch-resolve ASN for up to ``_BATCH_SIZE`` IPs. Never raises."""
    try:
        import httpx
    except ImportError:  # pragma: no cover - httpx is a hard project dep
        return {}

    payload = [{"query": ip} for ip in ips]
    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT_S) as client:
            resp = client.post(_BATCH_URL, json=payload)
        if resp.status_code != 200:
            return {}
        rows = resp.json()
    except Exception:  # noqa: BLE001 — fail open on any transport error
        return {}

    out: dict[str, dict[str, Any]] = {}
    now = time.time()
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or row.get("status") != "success":
            continue
        ip = str(row.get("query", ""))
        raw_as = str(row.get("as", ""))
        asn = 0
        if raw_as.upper().startswith("AS"):
            head = raw_as.split()[0][2:]
            if head.isdigit():
                asn = int(head)
        if not ip or not asn:
            continue
        out[ip] = {
            "asn": asn,
            "asname": str(row.get("asname", "")),
            "country": str(row.get("countryCode", "")),
            "ts": now,
        }
    return out


def resolve_asns(ips: Iterable[str]) -> dict[str, dict[str, Any]]:
    """Resolve ASN info for IPv4 literals, using and refreshing the disk cache.

    Cache misses are batched (100 per request, at most ``_MAX_BATCHES``
    requests per call). Returns only successfully resolved entries;
    unresolvable IPs are simply absent — callers must treat absence as
    "unknown, allow".
    """
    wanted = sorted({ip for ip in ips if _is_ipv4_literal(ip)})
    if not wanted:
        return {}

    cache = _load_cache()
    missing = [ip for ip in wanted if ip not in cache]

    batches = 0
    for start in range(0, len(missing), _BATCH_SIZE):
        if batches >= _MAX_BATCHES:
            _log.warning(
                "ASN lookup: capped at %d batches, %d hosts left unresolved",
                _MAX_BATCHES,
                len(missing) - start,
            )
            break
        chunk = missing[start : start + _BATCH_SIZE]
        if batches:
            time.sleep(1.5)  # stay well inside the free tier's rate limit
        cache.update(_lookup_uncached(chunk))
        batches += 1

    if batches:
        _save_cache(cache)

    return {ip: cache[ip] for ip in wanted if ip in cache}


def filter_blocked_asn(
    nodes: list[VlessNode],
    *,
    blocked: frozenset[int] = BLOCKED_ASNS,
    log_fn: Any = None,
) -> list[VlessNode]:
    """Drop candidates whose ASN is on the measured-blocklist.

    Nodes are stamped with ``extra["rejected_reason"] = "asn_blocked=AS<N>"``
    so the existing quarantine classifier in ``refresh_proxy_list`` can
    bucket them. Hostnames and unresolved hosts are always kept (fail open).

    Returns the surviving list, order preserved.
    """
    if not nodes:
        return []

    info = resolve_asns({n.host for n in nodes})
    if not info:
        return list(nodes)  # lookup unavailable — do not filter anything

    survivors: list[VlessNode] = []
    dropped: list[str] = []
    for node in nodes:
        entry = info.get(node.host)
        if entry is None:
            survivors.append(node)  # hostname or unresolved → allow
            continue
        asn = int(entry.get("asn") or 0)
        if asn in blocked:
            node.extra.setdefault("rejected_reason", f"asn_blocked=AS{asn}")
            dropped.append(f"{node.host}:{node.port}(AS{asn})")
            continue
        node.extra["asn"] = asn
        node.extra["asname"] = entry.get("asname", "")
        survivors.append(node)

    if dropped:
        msg = (
            f"ASN pre-filter: dropped {len(dropped)} candidate(s) from "
            f"measured-blocked ASNs — {', '.join(dropped[:6])}"
            + ("…" if len(dropped) > 6 else "")
        )
        if log_fn is not None:
            log_fn(msg)
        else:
            _log.info(msg)

    return survivors


def preferred_asn_count(nodes: Iterable[VlessNode]) -> int:
    """Diagnostic helper: how many nodes sit in PREFERRED_ASNS (cached only)."""
    cache = _load_cache()
    return sum(
        1
        for n in nodes
        if int((cache.get(n.host) or {}).get("asn") or 0) in PREFERRED_ASNS
    )


__all__ = [
    "BLOCKED_ASNS",
    "PREFERRED_ASNS",
    "filter_blocked_asn",
    "preferred_asn_count",
    "resolve_asns",
]
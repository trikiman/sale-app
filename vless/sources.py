"""Fetch VLESS URLs from upstream sources and geo-filter to RU exits.

Two responsibilities live here:

1. :func:`fetch_igareck_list` — download the raw newline-delimited list of
   VLESS URLs from the ``igareck/vpn-configs-for-russia`` public repo. Pure
   HTTP, no parsing. The URL is exposed as a module constant so tests can
   monkeypatch it.
2. :func:`filter_ru_nodes` — take a parsed ``list[VlessNode]`` and split it
   into ``(ru_nodes, rejected_nodes)`` using the existing consensus geo
   resolver in ``scripts/geo_providers.py`` (reused as-is per 56-CONTEXT
   D-05). Results are cached on disk by the resolver, so the second run over
   the same IPs is instant.

A module CLI (``python -m vless.sources``) fetches, parses, geo-filters, and
prints a one-line summary with a non-zero exit code if we end up with fewer
than five RU nodes — the floor below which the pool is not worth bringing
up.
"""
from __future__ import annotations

import argparse
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path

from vless.parser import VlessNode, parse_vless_list

# The igareck repo ships a family of VLESS lists under different names — black
# (RU-uplink-bypass) and white (CIDR/SNI-whitelist) lists, plus mobile variants.
# No single file consistently carries enough RU-exit reality nodes day to day,
# so the fetcher unions a curated set and lets ``parse_vless_list`` de-duplicate
# and drop non-reality entries. Kept as a tuple so callers can override.
IGARECK_BASE_URL = "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/"

IGARECK_VLESS_FILES: tuple[str, ...] = (
    "BLACK_VLESS_RUS.txt",
    "BLACK_VLESS_RUS_mobile.txt",
    "Vless-Reality-White-Lists-Rus-Mobile.txt",
    "Vless-Reality-White-Lists-Rus-Mobile-2.txt",
    "WHITE-CIDR-RU-all.txt",
    "WHITE-CIDR-RU-checked.txt",
    "WHITE-SNI-RU-all.txt",
)

# Default canonical URL — kept for backwards compatibility / docs. The live
# fetcher (:func:`fetch_igareck_list`) unions every file in IGARECK_VLESS_FILES.
IGARECK_VLESS_URL = IGARECK_BASE_URL + IGARECK_VLESS_FILES[0]

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CACHE_PATH = _REPO_ROOT / ".cache" / "ip_country.json"
_MIN_RU_NODES_FOR_OK = 5


def _fetch_one(url: str, *, timeout: float) -> str:
    """Fetch a single URL and return its decoded body."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def fetch_igareck_list(
    *,
    url: str | None = None,
    timeout: float = 20.0,
    files: tuple[str, ...] = IGARECK_VLESS_FILES,
    base_url: str = IGARECK_BASE_URL,
) -> str:
    """Download the VLESS URL list(s) and return them as a single text blob.

    By default fetches every file in :data:`IGARECK_VLESS_FILES` from the
    igareck repo and concatenates them with a blank line separator; line-level
    deduplication is left to :func:`vless.parser.parse_vless_list` via
    ``VlessNode`` identity at admission time.

    Passing an explicit ``url`` overrides the multi-file default — useful for
    tests that monkeypatch a local fixture or an alternate source repo.

    Individual file failures are tolerated (logged to stderr, body skipped)
    so a single 404 on a renamed list does not wipe the run. If *every* file
    fails, the last exception is re-raised so the caller sees a real network
    error instead of a silent empty result.
    """
    if url is not None:
        return _fetch_one(url, timeout=timeout)

    parts: list[str] = []
    last_exc: Exception | None = None
    for fname in files:
        full = base_url + fname
        try:
            parts.append(_fetch_one(full, timeout=timeout))
        except (urllib.error.URLError, socket.timeout, OSError) as exc:
            last_exc = exc
            print(f"[vless] skipped {fname}: {exc}", file=sys.stderr)
    if not parts and last_exc is not None:
        raise last_exc
    return "\n".join(parts)


def _resolve_host_ip(host: str) -> str | None:
    """Resolve a VLESS node's host to an IPv4 string.

    VLESS URLs can use a hostname or a literal IP. The geo resolver expects
    an IP, so we lift any hostname via DNS. Failures return ``None`` — the
    node is then treated as un-verifiable and rejected.
    """
    if not host:
        return None
    try:
        socket.inet_aton(host)
        return host
    except OSError:
        pass
    try:
        return socket.gethostbyname(host)
    except OSError:
        return None


def _build_default_resolver():
    """Construct the project's consensus geo resolver with the shared cache.

    Imported lazily so this module is importable without the ``scripts``
    package on ``sys.path`` (tests monkeypatch ``geo_resolver`` instead).
    """
    # Make the sibling ``scripts/`` package importable regardless of cwd.
    scripts_dir = str(_REPO_ROOT)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from scripts.geo_providers import MultiGeoResolver, build_default_providers

    cache_path = _DEFAULT_CACHE_PATH
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    return MultiGeoResolver(
        providers=build_default_providers(),
        cache_path=cache_path,
    )


# Russian-flag emoji (regional indicators R + U) — U+1F1F7 U+1F1FA. Some
# exporters lose the second regional indicator in transit, others insert a
# variation selector between them, so we match on the leading indicator and
# on the plain-text "russia" / "ru" fallbacks too.
_RU_FLAG = "\U0001f1f7\U0001f1fa"
_RU_FLAG_LEADER = "\U0001f1f7"  # regional indicator "R"
_RU_TEXT_MARKERS = ("russia", "россия", "рф", "ru ", "[ru]", "(ru)")


def _has_ru_marker(name: str) -> bool:
    """Return True when ``name`` contains an RU flag or textual marker.

    The igareck lists label every entry with ``🇷🇺 Russia [...]`` or
    ``🇷🇺 Russia [*CIDR]`` / ``🇷🇺 Russia [*SNI]``. Non-RU entries use
    other flags (🇺🇸, 🇩🇪, 🇳🇱, etc.), so a pure flag-based filter is
    enough to split RU-exit nodes from the rest without any external
    geo-DB query.
    """
    if not name:
        return False
    if _RU_FLAG in name or _RU_FLAG_LEADER in name:
        return True
    lowered = name.lower()
    return any(marker in lowered for marker in _RU_TEXT_MARKERS)


def filter_ru_nodes(
    nodes: list[VlessNode],
    *,
    geo_resolver=None,  # noqa: ARG001 — kept for signature compatibility
    min_agree: int = 2,  # noqa: ARG001 — kept for signature compatibility
) -> tuple[list[VlessNode], list[VlessNode]]:
    """Split ``nodes`` into ``(ru_nodes, rejected_nodes)`` by fragment label.

    Prior to v1.16 we ran every host through a multi-provider consensus geo
    resolver, but the igareck lists already label every entry with a country
    flag emoji in the URL fragment (the part after ``#``). Trusting that
    label is both faster (no DNS, no third-party API) and more accurate for
    our use case: the label reflects the *exit* country the operator cares
    about, whereas a geo-DB lookup on ``host`` returns the frontend IP —
    which is often a Cloudflare / OVH edge that doesn't map to the real
    egress.
    """
    if not nodes:
        return [], []

    ru_nodes: list[VlessNode] = []
    rejected_nodes: list[VlessNode] = []
    for node in nodes:
        if _has_ru_marker(node.name):
            ru_nodes.append(node)
        else:
            rejected_nodes.append(node)

    return ru_nodes, rejected_nodes


def _cli(argv: list[str] | None = None) -> int:
    """Module-level self-test CLI. Returns a shell exit code (0/1)."""
    parser = argparse.ArgumentParser(description="Fetch, parse, geo-filter VLESS list")
    parser.add_argument(
        "--url",
        default=None,
        help="Single VLESS list URL (default: union of IGARECK_VLESS_FILES)",
    )
    parser.add_argument(
        "--timeout", type=float, default=20.0, help="HTTP timeout in seconds"
    )
    parser.add_argument(
        "--skip-geo",
        action="store_true",
        help="Skip the geo-filter step (useful for quick parser smoke tests)",
    )
    args = parser.parse_args(argv)

    if args.url:
        print(f"[vless] fetching {args.url}")
    else:
        print(
            "[vless] fetching igareck union "
            f"({len(IGARECK_VLESS_FILES)} files from {IGARECK_BASE_URL})"
        )
    try:
        text = fetch_igareck_list(url=args.url, timeout=args.timeout)
    except (urllib.error.URLError, socket.timeout, OSError) as exc:
        print(f"[vless] fetch failed: {exc}", file=sys.stderr)
        return 1

    nodes, errors = parse_vless_list(text)
    print(
        f"[vless] parsed: {len(nodes)} nodes, {len(errors)} parse errors "
        f"(from {len(text.splitlines())} lines)"
    )
    for lineno, _raw, reason in errors[:5]:
        print(f"[vless]   parse error line {lineno}: {reason}")

    if args.skip_geo:
        sample = nodes[:3]
        for node in sample:
            print(f"[vless] sample: {node.host}:{node.port} — {node.name}")
        return 0 if len(nodes) >= _MIN_RU_NODES_FOR_OK else 1

    ru_nodes, rejected = filter_ru_nodes(nodes)
    print(
        f"[vless] geo-filter: {len(ru_nodes)} RU, "
        f"{len(rejected)} rejected (non-RU or DNS failure)"
    )
    for node in ru_nodes[:3]:
        print(f"[vless]   RU sample: {node.host}:{node.port} — {node.name}")

    # Write a representative xray config so operators (and plan 56-02) can
    # inspect what the generator would hand to the bridge. No xray process is
    # started here — this is a structural smoke test only.
    if ru_nodes:
        import json

        from vless.config_gen import build_xray_config

        sample_path = _REPO_ROOT / ".cache" / "vless_sample_config.json"
        sample_path.parent.mkdir(parents=True, exist_ok=True)
        config = build_xray_config(ru_nodes)
        sample_path.write_text(
            json.dumps(config, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        # Cheap structural smoke check: round-trip must succeed and must keep
        # the outbound count in sync with the RU node count.
        parsed = json.loads(sample_path.read_text(encoding="utf-8"))
        vless_outbounds = [ob for ob in parsed["outbounds"] if ob.get("protocol") == "vless"]
        assert len(vless_outbounds) == len(ru_nodes), (
            f"config drift: {len(vless_outbounds)} outbounds vs {len(ru_nodes)} RU nodes"
        )
        print(f"[vless] wrote sample config to {sample_path} ({len(ru_nodes)} outbounds)")

    return 0 if len(ru_nodes) >= _MIN_RU_NODES_FOR_OK else 1


if __name__ == "__main__":
    sys.exit(_cli())

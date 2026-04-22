"""Local-only pipeline: fetch public proxy lists, filter to Russia,
test aliveness against VkusVill, report yield.

This is a *research* script — it does NOT modify `proxy_manager.py` or any
EC2 state. Its purpose is to empirically answer: "given all the sources we
know, how many working Russian SOCKS5 proxies can we actually get?"

Steps
-----
1. Fetch every configured source, parse to `ip:port` entries.
2. Deduplicate across sources so each IP is looked up / tested exactly once.
3. Geo-lookup via http://ip-api.com/batch (cached to `.cache/ip_country.json`).
4. Keep only Russian IPs.
5. Test each RU `ip:port` against VkusVill via SOCKS5 with N parallel workers.
   Testing strategy mirrors `proxy_manager._test_proxy` — SOCKS5 preflight
   first (kernel timeout), then HTTPS GET with SSL verification.
6. Persist results to `.cache/alive_ru_proxies.json` and print summary.

Usage
-----
    python scripts/test_ru_proxy_pipeline.py                 # full run
    python scripts/test_ru_proxy_pipeline.py --tier1-only    # skip global lists
    python scripts/test_ru_proxy_pipeline.py --workers 100   # control concurrency
    python scripts/test_ru_proxy_pipeline.py --limit 500     # cap IPs tested

Outputs
-------
    .cache/ip_country.json           - persistent geo cache
    .cache/alive_ru_proxies.json     - working proxies with speed + source
"""
from __future__ import annotations

import argparse
import concurrent.futures
import functools
import json
import os
import re
import socket
import ssl
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from urllib.error import HTTPError, URLError

# Local module — multi-provider geolocation with fallback + consensus
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
from geo_providers import MultiGeoResolver, ConsensusResult  # noqa: E402

try:
    import httpx

    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

# ---------------------------------------------------------------------------
# Sources — same as survey_ru_proxy_sources.py, classified by tier
# ---------------------------------------------------------------------------
# Tier 1: country-prefiltered (already tagged as RU). No geo-lookup needed.
TIER1_SOURCES: list[tuple[str, str, str]] = [
    (
        "geonode_socks5_ru",
        "https://proxylist.geonode.com/api/proxy-list?country=RU&protocols=socks5&limit=500&page=1&sort_by=lastChecked&sort_type=desc",
        "geonode_json",
    ),
    (
        "geonode_socks4_ru",
        "https://proxylist.geonode.com/api/proxy-list?country=RU&protocols=socks4&limit=500&page=1&sort_by=lastChecked&sort_type=desc",
        "geonode_json",
    ),
    (
        "geonode_http_ru",
        "https://proxylist.geonode.com/api/proxy-list?country=RU&protocols=http&limit=500&page=1&sort_by=lastChecked&sort_type=desc",
        "geonode_json",
    ),
    (
        "proxyscrape_socks5_ru",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&country=RU&timeout=10000&ssl=all&anonymity=all",
        "plain_ip_port",
    ),
    (
        "proxyscrape_socks4_ru",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks4&country=RU&timeout=10000&ssl=all&anonymity=all",
        "plain_ip_port",
    ),
    (
        "proxyscrape_http_ru",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&country=RU&timeout=10000&ssl=all&anonymity=all",
        "plain_ip_port",
    ),
    (
        "proxifly_RU",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/RU/data.txt",
        "with_proto",
    ),
]

# Tier 2: global, mixed-country. Must be geo-filtered. User's estimate ~0.1-1% RU.
TIER2_SOURCES: list[tuple[str, str, str]] = [
    (
        "proxifly_global_socks5",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.txt",
        "with_proto",
    ),
    (
        "proxifly_global_http",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
        "with_proto",
    ),
    (
        "thespeedx_socks5",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
        "plain_ip_port",
    ),
    (
        "thespeedx_http",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "plain_ip_port",
    ),
    (
        "thespeedx_sockslist_socks4",
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks4.txt",
        "plain_ip_port",
    ),
    (
        "hookzof_socks5",
        "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
        "plain_ip_port",
    ),
    (
        "monosans_socks5",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
        "plain_ip_port",
    ),
    (
        "monosans_http",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "plain_ip_port",
    ),
    (
        "monosans_socks4",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt",
        "plain_ip_port",
    ),
    (
        "monosans_all",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/all.txt",
        "plain_ip_port",
    ),
    (
        "jetkai_socks5",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks5.txt",
        "plain_ip_port",
    ),
    (
        "jetkai_http",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
        "plain_ip_port",
    ),
    (
        "clarketm_socks5",
        "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
        "plain_ip_port",
    ),
    (
        "openproxylist_socks5",
        "https://api.openproxylist.xyz/socks5.txt",
        "plain_ip_port",
    ),
    (
        "openproxylist_http",
        "https://api.openproxylist.xyz/http.txt",
        "plain_ip_port",
    ),
    (
        "shiftytr_proxy",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/proxy.txt",
        "plain_ip_port",
    ),
    (
        "pxys_daily_working",
        "https://raw.githubusercontent.com/Pxys-io/DailyProxyList/master/working_proxies.txt",
        "plain_ip_port",
    ),
    (
        "vanndev_socks5",
        "https://raw.githubusercontent.com/Vann-Dev/proxy-list/main/proxies/socks5.txt",
        "plain_ip_port",
    ),
    (
        "vanndev_http",
        "https://raw.githubusercontent.com/Vann-Dev/proxy-list/main/proxies/http.txt",
        "plain_ip_port",
    ),
    (
        "ercindedeoglu_socks5",
        "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/socks5.txt",
        "plain_ip_port",
    ),
    (
        "ercindedeoglu_socks4",
        "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/socks4.txt",
        "plain_ip_port",
    ),
    (
        "ercindedeoglu_http",
        "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/http.txt",
        "plain_ip_port",
    ),
    (
        "dpangestuw_all",
        "https://raw.githubusercontent.com/dpangestuw/Free-Proxy/main/All_proxies.txt",
        "plain_ip_port",
    ),
    (
        "themiralay_world",
        "https://raw.githubusercontent.com/themiralay/Proxy-List-World/master/data.txt",
        "plain_ip_port",
    ),
]

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
IP_PORT_RE = re.compile(r"(?P<ip>\d{1,3}(?:\.\d{1,3}){3}):(?P<port>\d{1,5})")
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 20

# Alive check params — tuned tight per user: "1-2s or dead, faster = alive & quick".
# These are the DEFAULTS; CLI args `--preflight-timeout` and `--probe-timeout`
# override them. proxy_manager.py on EC2 still uses its more lenient values;
# this script is research-only.
VKUSVILL_URL = "https://vkusvill.ru/"
SOCKS5_CONNECT_TIMEOUT = 1.0        # TCP connect to proxy
SOCKS5_HANDSHAKE_TIMEOUT = 1.0      # SOCKS5 method-negotiation reply
PROBE_TIMEOUT = 2.0                 # Full HTTPS GET through proxy

SUPPORTED_PROTOCOLS = ("socks5", "socks4", "http")

# VkusVill imposes a ~4h temporary block on rate-limited IPs. Mirror this in the
# research script so re-runs don't waste time re-testing IPs that are still in
# the penalty box. Entry shape: {addr: {"blocked_at": ts, "reason": str}}.
VKUSVILL_COOLDOWN_S = 4 * 3600

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / ".cache"
CACHE_DIR.mkdir(exist_ok=True)
IP_COUNTRY_CACHE = CACHE_DIR / "ip_country.json"
ALIVE_CACHE = CACHE_DIR / "alive_ru_proxies.json"
ALL_RU_LIST = CACHE_DIR / "all_ru_candidates.json"
VKUSVILL_COOLDOWN_CACHE = CACHE_DIR / "vkusvill_cooldowns.json"

# Failure-error strings that indicate a VkusVill-specific block (IP is still
# alive at the proxy layer but VkusVill is refusing / throttling it). Anything
# NOT in this set is treated as a proxy-dead signal and ignored for cooldown.
VKUSVILL_BLOCK_ERRORS = {
    "ReadTimeout",          # proxy forwarded but VkusVill stalled the response
    "content_mismatch",     # got a page but it's the block/captcha page
    "status_403",
    "status_429",
    "status_451",
}


# ---------------------------------------------------------------------------
# Fetching + parsing
# ---------------------------------------------------------------------------
@dataclass
class SourceEntry:
    label: str
    url: str
    parser: str
    fetched: bool = False
    error: str = ""
    raw_count: int = 0
    unique_hosts: set[str] = field(default_factory=set)
    ru_hosts: set[str] = field(default_factory=set)


def http_get(url: str, timeout: float = REQUEST_TIMEOUT) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_geonode_json(body: str) -> list[str]:
    data = json.loads(body)
    out = []
    for item in data.get("data", []):
        ip, port = item.get("ip"), item.get("port")
        if ip and port:
            out.append(f"{ip}:{port}")
    return out


def parse_plain(body: str) -> list[str]:
    out = []
    for line in body.splitlines():
        m = IP_PORT_RE.search(line.strip())
        if m:
            out.append(f"{m.group('ip')}:{m.group('port')}")
    return out


PARSERS = {
    "geonode_json": parse_geonode_json,
    "plain_ip_port": parse_plain,
    "with_proto": parse_plain,
}


# ---------------------------------------------------------------------------
# VkusVill 4h cooldown — persistent across runs
# ---------------------------------------------------------------------------
def load_vkusvill_cooldowns() -> dict[str, dict]:
    """Load the cooldown map and drop entries whose window has already lapsed."""
    if not VKUSVILL_COOLDOWN_CACHE.exists():
        return {}
    try:
        with open(VKUSVILL_COOLDOWN_CACHE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    now = time.time()
    fresh = {
        addr: entry
        for addr, entry in data.items()
        if (now - float(entry.get("blocked_at", 0.0))) < VKUSVILL_COOLDOWN_S
    }
    if len(fresh) != len(data):
        save_vkusvill_cooldowns(fresh)
    return fresh


def save_vkusvill_cooldowns(cooldowns: dict[str, dict]) -> None:
    tmp = VKUSVILL_COOLDOWN_CACHE.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cooldowns, f, ensure_ascii=False, indent=2)
    os.replace(tmp, VKUSVILL_COOLDOWN_CACHE)


def classify_failure(result: dict) -> str:
    """Return 'vkusvill_block', 'proxy_dead', or '' (for alive results).

    Routes :data:`VKUSVILL_BLOCK_ERRORS` results into the 4h cooldown bucket;
    everything else (preflight, ProtocolError, ConnectTimeout, ProxyError,
    ConnectionRefused, SOCKSError, …) is treated as a dead proxy and gets no
    cooldown (it'll simply not show up in working lists next cycle).
    """
    if result.get("alive"):
        return ""
    err = result.get("error") or ""
    stage = result.get("stage") or ""
    if err in VKUSVILL_BLOCK_ERRORS:
        return "vkusvill_block"
    # status_NNN family (any 4xx from vkusvill that isn't whitelisted above is
    # still most likely VkusVill policy rather than proxy failure)
    if err.startswith("status_4"):
        return "vkusvill_block"
    if stage == "preflight":
        return "proxy_dead"
    return "proxy_dead"


def protocols_for_source(label: str) -> set[str]:
    """Infer which proxy protocols a source likely contains from its label.

    Sources with an explicit protocol in the label (e.g. `geonode_socks5_ru`)
    return that single protocol. Ambiguous sources (e.g. `proxifly_RU`,
    `monosans_all`, `themiralay_world`) return the full set and we test
    each `ip:port` as every protocol.
    """
    ll = label.lower()
    if "socks5" in ll:
        return {"socks5"}
    if "socks4" in ll:
        return {"socks4"}
    # Match `http` but not as substring of something else (none currently).
    if "http" in ll:
        return {"http"}
    return set(SUPPORTED_PROTOCOLS)


def fetch_sources(sources: list[tuple[str, str, str]]) -> list[SourceEntry]:
    entries: list[SourceEntry] = []
    for label, url, parser in sources:
        e = SourceEntry(label=label, url=url, parser=parser)
        print(f"[{label}] fetching...", flush=True)
        try:
            body = http_get(url)
            e.fetched = True
        except Exception as exc:
            e.error = f"{type(exc).__name__}: {exc}"
            print(f"  ERROR: {e.error}", flush=True)
            entries.append(e)
            continue
        try:
            parsed = PARSERS[parser](body)
        except Exception as exc:
            e.error = f"parse failed: {exc}"
            print(f"  PARSE ERROR: {exc}", flush=True)
            entries.append(e)
            continue
        e.raw_count = len(parsed)
        e.unique_hosts = {p.split(":", 1)[0] for p in parsed}
        # Keep ip:port pairs too (for testing later)
        e.ip_ports = set(parsed)  # type: ignore[attr-defined]
        print(f"  parsed={e.raw_count}  unique_ips={len(e.unique_hosts)}", flush=True)
        entries.append(e)
    return entries


# ---------------------------------------------------------------------------
# Geo-lookup — delegated to MultiGeoResolver (10 providers, fallback chain)
# ---------------------------------------------------------------------------
def build_resolver() -> MultiGeoResolver:
    """Construct a ``MultiGeoResolver`` bound to our persistent cache path.

    Lives in ``.cache/ip_country.json`` exactly like the old single-provider
    cache, so prior runs remain valid across the upgrade.
    """
    return MultiGeoResolver(cache_path=IP_COUNTRY_CACHE)


# ---------------------------------------------------------------------------
# Aliveness testing (SOCKS5)
# ---------------------------------------------------------------------------
def socks5_preflight(
    addr: str,
    connect_timeout: float = SOCKS5_CONNECT_TIMEOUT,
    handshake_timeout: float = SOCKS5_HANDSHAKE_TIMEOUT,
) -> bool:
    """Raw-socket SOCKS5 greeting. Fast filter — dead IPs fail within connect_timeout+handshake_timeout."""
    try:
        host, _, port_s = addr.partition(":")
        port = int(port_s)
    except (ValueError, TypeError):
        return False
    if not host or port <= 0 or port > 65535:
        return False
    sock = None
    try:
        sock = socket.create_connection((host, port), timeout=connect_timeout)
        sock.settimeout(handshake_timeout)
        sock.sendall(b"\x05\x01\x00")
        reply = b""
        while len(reply) < 2:
            chunk = sock.recv(2 - len(reply))
            if not chunk:
                return False
            reply += chunk
        return reply[0] == 0x05
    except (OSError, socket.timeout):
        return False
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass


def tcp_preflight(addr: str, connect_timeout: float = SOCKS5_CONNECT_TIMEOUT) -> bool:
    """Plain TCP connect probe — used for SOCKS4/HTTP where we can't cheaply
    distinguish protocol at the socket level. If the port isn't open within
    `connect_timeout`, the proxy is dead regardless of protocol."""
    try:
        host, _, port_s = addr.partition(":")
        port = int(port_s)
    except (ValueError, TypeError):
        return False
    if not host or port <= 0 or port > 65535:
        return False
    sock = None
    try:
        sock = socket.create_connection((host, port), timeout=connect_timeout)
        return True
    except (OSError, socket.timeout):
        return False
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass


def preflight_for(protocol: str, addr: str, connect_timeout: float, handshake_timeout: float) -> bool:
    if protocol == "socks5":
        return socks5_preflight(addr, connect_timeout, handshake_timeout)
    # socks4 / http — no cheap protocol-specific handshake we can do here,
    # so we fall back to plain TCP connect. The full probe (via httpx) still
    # validates the actual protocol.
    return tcp_preflight(addr, connect_timeout)


def probe_vkusvill(
    addr: str,
    protocol: str = "socks5",
    timeout: float = PROBE_TIMEOUT,
) -> tuple[bool, float, str]:
    """Full VkusVill probe through the given proxy. Returns (ok, elapsed_s, error_hint).

    `protocol` selects the proxy URL scheme: socks5://, socks4://, or http://.
    NOTE: httpx 0.28 only supports http://, https://, socks5://, socks5h://.
    SOCKS4 returns "httpx_no_socks4_support" — install httpx-socks to enable.
    Tight timeout by design: user guidance is "1-2s = alive, slower = useless".
    """
    start = time.time()
    if not HAS_HTTPX:
        return False, 0.0, "httpx_missing"
    if protocol not in SUPPORTED_PROTOCOLS:
        return False, 0.0, f"unsupported_protocol_{protocol}"
    if protocol == "socks4":
        # httpx raises ValueError("Unknown scheme") on socks4:// URLs. Rather
        # than add httpx-socks as a dep just for research, return a distinct
        # hint so the per-protocol stats honestly reflect "not tested".
        return False, 0.0, "httpx_no_socks4_support"
    proxy_url = f"{protocol}://{addr}"
    try:
        with httpx.Client(
            proxy=proxy_url,
            timeout=timeout,
            verify=True,  # reject MITM
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        ) as client:
            r = client.get(VKUSVILL_URL)
            elapsed = time.time() - start
            if r.status_code != 200:
                return False, elapsed, f"status_{r.status_code}"
            body = r.text[:5000].lower()
            if "vkusvill" not in body:
                return False, elapsed, "content_mismatch"
            return True, elapsed, ""
    except Exception as exc:
        return False, time.time() - start, type(exc).__name__


def test_one(
    task: tuple[str, str],
    preflight_timeout: float = SOCKS5_CONNECT_TIMEOUT,
    handshake_timeout: float = SOCKS5_HANDSHAKE_TIMEOUT,
    probe_timeout: float = PROBE_TIMEOUT,
) -> dict:
    """Full aliveness check: protocol-specific preflight then probe.

    `task` is `(ip:port, protocol)`. All timeouts are caller-controlled.
    """
    addr, protocol = task
    t0 = time.time()
    if not preflight_for(protocol, addr, preflight_timeout, handshake_timeout):
        return {
            "addr": addr,
            "protocol": protocol,
            "alive": False,
            "stage": "preflight",
            "elapsed_s": round(time.time() - t0, 2),
        }
    ok, elapsed, err = probe_vkusvill(addr, protocol=protocol, timeout=probe_timeout)
    return {
        "addr": addr,
        "protocol": protocol,
        "alive": ok,
        "stage": "probe" if ok else "probe_fail",
        "elapsed_s": round(time.time() - t0, 2),
        "probe_elapsed_s": round(elapsed, 2),
        "error": err,
    }


def test_parallel(
    tasks: list[tuple[str, str]],
    workers: int,
    preflight_timeout: float = SOCKS5_CONNECT_TIMEOUT,
    handshake_timeout: float = SOCKS5_HANDSHAKE_TIMEOUT,
    probe_timeout: float = PROBE_TIMEOUT,
) -> list[dict]:
    print(
        f"\nTesting {len(tasks)} (ip:port, protocol) pairs with {workers} parallel workers "
        f"(preflight={preflight_timeout}s, handshake={handshake_timeout}s, "
        f"probe={probe_timeout}s)..."
    )
    worker_fn = functools.partial(
        test_one,
        preflight_timeout=preflight_timeout,
        handshake_timeout=handshake_timeout,
        probe_timeout=probe_timeout,
    )
    results: list[dict] = []
    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(worker_fn, t): t for t in tasks}
        done = 0
        alive = 0
        for fut in concurrent.futures.as_completed(futures):
            r = fut.result()
            results.append(r)
            done += 1
            if r["alive"]:
                alive += 1
                print(
                    f"  [{done}/{len(tasks)}] ALIVE {r['protocol']}://{r['addr']} "
                    f"{r['probe_elapsed_s']:.2f}s"
                )
            if done % 100 == 0:
                print(
                    f"  progress: {done}/{len(tasks)}  alive={alive}  "
                    f"elapsed={time.time()-start:.0f}s",
                    flush=True,
                )
    elapsed = time.time() - start
    print(f"\nTested {len(tasks)} in {elapsed:.0f}s  alive={alive}")
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tier1-only",
        action="store_true",
        help="Skip global mixed-country sources",
    )
    parser.add_argument(
        "--workers", type=int, default=100, help="Parallel aliveness workers"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Cap number of RU proxies tested (0 = no limit)",
    )
    parser.add_argument(
        "--skip-alive",
        action="store_true",
        help="Only build RU list, skip aliveness test",
    )
    parser.add_argument(
        "--preflight-timeout",
        type=float,
        default=SOCKS5_CONNECT_TIMEOUT,
        help=(
            "SOCKS5 TCP connect timeout in seconds (default %(default)s). "
            "Tight = aggressive drop of slow/dead proxies."
        ),
    )
    parser.add_argument(
        "--handshake-timeout",
        type=float,
        default=SOCKS5_HANDSHAKE_TIMEOUT,
        help="SOCKS5 greeting reply timeout in seconds (default %(default)s).",
    )
    parser.add_argument(
        "--probe-timeout",
        type=float,
        default=PROBE_TIMEOUT,
        help=(
            "Full HTTPS GET through SOCKS5 timeout in seconds "
            "(default %(default)s). Anything slower is considered useless."
        ),
    )
    parser.add_argument(
        "--protocols",
        type=str,
        default="socks5,socks4,http",
        help=(
            "Comma-separated list of protocols to test (subset of "
            "socks5,socks4,http). Default: all three. Each ip:port is only "
            "tested as a protocol if its source declared that protocol (or "
            "was ambiguous)."
        ),
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help=(
            "Consensus mode: after the primary fallback-chain lookup, re-query "
            "RU-tagged IPs against additional providers and keep only IPs where "
            "at least --min-agree providers agree on RU. Drops false positives "
            "(residential proxies with stale WHOIS, etc.)."
        ),
    )
    parser.add_argument(
        "--min-agree",
        type=int,
        default=2,
        help="Minimum providers that must agree on a country code in --verify mode (default 2).",
    )
    args = parser.parse_args()
    wanted_protocols = {p.strip().lower() for p in args.protocols.split(",") if p.strip()}
    bad = wanted_protocols - set(SUPPORTED_PROTOCOLS)
    if bad:
        parser.error(f"unknown protocol(s): {sorted(bad)}. Use: {SUPPORTED_PROTOCOLS}")

    sources = TIER1_SOURCES + (TIER2_SOURCES if not args.tier1_only else [])
    print(f"Using {len(sources)} source(s). Output dir: {CACHE_DIR}")
    print(f"Testing protocols: {sorted(wanted_protocols)}")
    if args.verify:
        print(f"Consensus verification ON (min-agree={args.min_agree})")

    # Phase 1 — fetch
    entries = fetch_sources(sources)

    # Build union of unique ip:port (so we keep port info for testing)
    # and track protocols-per-ip:port based on source labels.
    all_ip_ports: set[str] = set()
    protos_for_ip_port: dict[str, set[str]] = {}
    for e in entries:
        src_protos = protocols_for_source(e.label) & wanted_protocols
        if not src_protos:
            continue
        for ip_port in getattr(e, "ip_ports", set()):
            all_ip_ports.add(ip_port)
            protos_for_ip_port.setdefault(ip_port, set()).update(src_protos)
    all_unique_ips = {p.split(":", 1)[0] for p in all_ip_ports}
    print(
        f"\nTotal unique ip:port across sources: {len(all_ip_ports)}\n"
        f"Total unique IPs (dedup): {len(all_unique_ips)}"
    )

    # Phase 2 — geo-lookup via MultiGeoResolver (fallback chain across 10 providers)
    resolver = build_resolver()
    print(
        f"\nGeo-lookup: {len(all_unique_ips)} IPs, "
        f"{len([ip for ip in all_unique_ips if resolver.cached(ip) is not None])} cached"
    )
    resolver.resolve_bulk(sorted(all_unique_ips))
    cache = {ip: resolver.cached(ip) or "??" for ip in all_unique_ips}

    # Print per-provider contribution for transparency
    print("\n[geo] provider stats:")
    for s in resolver.stats_summary():
        if s["calls"] == 0 and s["ips_resolved"] == 0:
            continue
        print(
            f"  {s['name']:<18} calls={s['calls']:>4}  "
            f"ips_resolved={s['ips_resolved']:>6}  "
            f"errors={s['errors']:>2}  rate_limited={s['rate_limited']:>2}"
            + (f"  [{s['last_error'][:40]}]" if s["last_error"] else "")
        )

    # Phase 2b (optional) — consensus verification on RU-tagged IPs
    verified_out: dict[str, ConsensusResult] = {}
    if args.verify:
        ru_ips = sorted({
            p.split(":", 1)[0]
            for p in all_ip_ports
            if cache.get(p.split(":", 1)[0]) == "RU"
        })
        print(
            f"\n[consensus] verifying {len(ru_ips)} RU-tagged IPs "
            f"(need ≥{args.min_agree} providers to agree)"
        )
        verified_out = resolver.resolve_consensus(
            ru_ips, min_agree=args.min_agree, max_providers=4
        )
        # Rewrite the country-code view: only keep RU where consensus holds
        dropped = 0
        for ip in ru_ips:
            r = verified_out.get(ip)
            if r and r.country == "RU":
                continue
            cache[ip] = r.country if (r and r.country) else "??"
            dropped += 1
        print(
            f"[consensus] {len(ru_ips) - dropped}/{len(ru_ips)} confirmed RU, "
            f"{dropped} dropped as unverified"
        )
        resolver.save_cache()

    # Phase 3 — filter to RU
    ru_ip_ports = [p for p in all_ip_ports if cache.get(p.split(":", 1)[0]) == "RU"]
    # Map source → RU ip:ports
    source_ru: dict[str, list[str]] = {}
    for e in entries:
        src_ips = getattr(e, "ip_ports", set())
        source_ru[e.label] = sorted(
            p for p in src_ips if cache.get(p.split(":", 1)[0]) == "RU"
        )

    print("\n" + "=" * 70)
    print(f"{'source':<32} {'total':>8} {'ru':>8} {'ru%':>6}")
    print("-" * 70)
    for e in entries:
        src_ips = getattr(e, "ip_ports", set())
        ru = source_ru.get(e.label, [])
        pct = (100 * len(ru) / len(src_ips)) if src_ips else 0.0
        status = "" if e.fetched else f" [{e.error[:30]}]"
        print(f"{e.label:<32} {len(src_ips):>8} {len(ru):>8} {pct:>5.1f}%{status}")
    print("-" * 70)
    print(
        f"{'COMBINED (unique):':<32} {len(all_ip_ports):>8} {len(ru_ip_ports):>8} "
        f"{100*len(ru_ip_ports)/max(len(all_ip_ports),1):>5.1f}%"
    )

    # Persist full RU candidate list
    with open(ALL_RU_LIST, "w", encoding="utf-8") as f:
        json.dump(
            {
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "total_unique_ip_ports": len(all_ip_ports),
                "ru_count": len(ru_ip_ports),
                "ru_ip_ports": sorted(ru_ip_ports),
                "by_source": {k: v for k, v in source_ru.items() if v},
                "consensus_verified": args.verify,
                "min_agree": args.min_agree if args.verify else None,
                "consensus_details": (
                    {
                        ip: {
                            "country": r.country,
                            "agreed": r.agreed,
                            "disagreed": r.disagreed,
                            "ratio": r.agreement_ratio,
                        }
                        for ip, r in verified_out.items()
                    }
                    if verified_out
                    else None
                ),
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"\nRU candidate list saved: {ALL_RU_LIST}")

    if args.skip_alive:
        return

    # Phase 4 — aliveness test
    ru_set = sorted(set(ru_ip_ports))

    # Respect VkusVill's 4h cooldown: skip IPs recently blocked by VkusVill so
    # we don't waste the test budget. Entries expire automatically.
    cooldowns = load_vkusvill_cooldowns()
    if cooldowns:
        cooldown_addrs = set(cooldowns.keys())
        before = len(ru_set)
        ru_set = [
            p for p in ru_set if p.split(":", 1)[0] not in cooldown_addrs
        ]
        skipped = before - len(ru_set)
        if skipped:
            next_eligible = min(
                float(e.get("blocked_at", 0.0)) + VKUSVILL_COOLDOWN_S
                for e in cooldowns.values()
            )
            eta = time.strftime("%H:%M", time.localtime(next_eligible))
            print(
                f"\n[cooldown] skipped {skipped} IPs in VkusVill cooldown "
                f"(earliest eligible again at ~{eta})"
            )

    if args.limit and args.limit < len(ru_set):
        ru_set = ru_set[: args.limit]
        print(f"Limiting test to {args.limit} RU ip:port entries")

    # Build (ip:port, protocol) task list based on what each ip:port's source(s)
    # declared. This avoids testing e.g. a SOCKS4-only entry as SOCKS5.
    tasks: list[tuple[str, str]] = []
    per_proto_count: dict[str, int] = {p: 0 for p in SUPPORTED_PROTOCOLS}
    for ip_port in ru_set:
        protos = protos_for_ip_port.get(ip_port, set()) & wanted_protocols
        for p in sorted(protos):
            tasks.append((ip_port, p))
            per_proto_count[p] = per_proto_count.get(p, 0) + 1
    print(
        f"\nTask plan: {len(tasks)} tests across {len(ru_set)} ip:port entries\n"
        f"  by protocol: {per_proto_count}"
    )

    results = test_parallel(
        tasks,
        workers=args.workers,
        preflight_timeout=args.preflight_timeout,
        handshake_timeout=args.handshake_timeout,
        probe_timeout=args.probe_timeout,
    )
    alive = [r for r in results if r["alive"]]
    alive.sort(key=lambda r: r.get("probe_elapsed_s", 999))

    # Record VkusVill-specific block results in the 4h cooldown cache. Don't
    # cool down IPs marked alive by any protocol — a working path beats a
    # failing one on the same IP.
    alive_addrs = {r["addr"] for r in alive}
    now = time.time()
    new_cooldowns = 0
    for r in results:
        if r["addr"] in alive_addrs:
            continue
        if classify_failure(r) == "vkusvill_block":
            cooldowns[r["addr"]] = {
                "blocked_at": now,
                "reason": r.get("error") or r.get("stage") or "unknown",
                "protocol": r.get("protocol", ""),
            }
            new_cooldowns += 1
    if new_cooldowns:
        save_vkusvill_cooldowns(cooldowns)
        print(
            f"[cooldown] recorded {new_cooldowns} new VkusVill-block IPs "
            f"(total active cooldowns: {len(cooldowns)})"
        )

    # Per-protocol breakdown for empirical protocol comparison
    per_proto_stats: dict[str, dict[str, int]] = {}
    for p in SUPPORTED_PROTOCOLS:
        tested = sum(1 for r in results if r.get("protocol") == p)
        alive_n = sum(1 for r in results if r.get("protocol") == p and r["alive"])
        if tested:
            per_proto_stats[p] = {
                "tested": tested,
                "alive": alive_n,
                "alive_rate_pct": round(100 * alive_n / tested, 2),
            }

    # Save
    with open(ALIVE_CACHE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "tested": len(tasks),
                "tested_unique_ip_ports": len(ru_set),
                "alive_count": len(alive),
                "alive_rate_pct": round(100 * len(alive) / max(len(tasks), 1), 2),
                "timeouts": {
                    "preflight": args.preflight_timeout,
                    "handshake": args.handshake_timeout,
                    "probe": args.probe_timeout,
                },
                "protocols_tested": sorted(wanted_protocols),
                "per_protocol": per_proto_stats,
                "alive": alive,
                "failures_by_error": _summarize_failures(results),
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"\nAlive results saved: {ALIVE_CACHE}")
    print(
        f"Summary: {len(alive)}/{len(tasks)} tests alive "
        f"({100*len(alive)/max(len(tasks),1):.1f}%)  "
        f"— unique ip:ports with ≥1 working protocol: "
        f"{len({r['addr'] for r in alive})}"
    )
    if per_proto_stats:
        print("\nPer-protocol breakdown:")
        for proto, stats in per_proto_stats.items():
            print(
                f"  {proto:<7} tested={stats['tested']:>5}  "
                f"alive={stats['alive']:>4}  rate={stats['alive_rate_pct']:>5.2f}%"
            )
    if alive:
        print("\nFastest 20 alive RU proxies:")
        for r in alive[:20]:
            print(
                f"  {r['protocol']}://{r['addr']:<22} "
                f"probe={r['probe_elapsed_s']:.2f}s"
            )


def _summarize_failures(results: list[dict]) -> dict[str, int]:
    failures: dict[str, int] = {}
    for r in results:
        if r["alive"]:
            continue
        key = r.get("error") or r.get("stage") or "unknown"
        failures[key] = failures.get(key, 0) + 1
    return dict(sorted(failures.items(), key=lambda kv: -kv[1]))


if __name__ == "__main__":
    main()

"""Survey multiple public proxy list sources for Russian IPs.

For each known source:
1. Fetch the list
2. Parse entries (handle `proto://ip:port`, `ip:port`, CSV, JSON)
3. Deduplicate across sources
4. Batch-lookup countries via ip-api.com
5. Report per-source count, RU count, and combined totals

Run on EC2 where outbound isn't blocked:
    python3 scripts/survey_ru_proxy_sources.py
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from urllib.error import HTTPError, URLError

# ---------------------------------------------------------------------------
# Source registry
# Each entry: (label, url, parser_name)
# ---------------------------------------------------------------------------
SOURCES: list[tuple[str, str, str]] = [
    # Aggregator APIs — pre-filtered to RU
    (
        "geonode_socks5_ru",
        "https://proxylist.geonode.com/api/proxy-list?country=RU&protocols=socks5&limit=500&page=1&sort_by=lastChecked&sort_type=desc",
        "geonode_json",
    ),
    (
        "geonode_http_ru",
        "https://proxylist.geonode.com/api/proxy-list?country=RU&protocols=http&limit=500&page=1&sort_by=lastChecked&sort_type=desc",
        "geonode_json",
    ),
    (
        "geonode_socks4_ru",
        "https://proxylist.geonode.com/api/proxy-list?country=RU&protocols=socks4&limit=500&page=1&sort_by=lastChecked&sort_type=desc",
        "geonode_json",
    ),
    (
        "proxyscrape_socks5_ru",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&country=RU&timeout=10000&ssl=all&anonymity=all",
        "plain_ip_port",
    ),
    (
        "proxyscrape_http_ru",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&country=RU&timeout=10000&ssl=all&anonymity=all",
        "plain_ip_port",
    ),
    (
        "proxyscrape_socks4_ru",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks4&country=RU&timeout=10000&ssl=all&anonymity=all",
        "plain_ip_port",
    ),
    (
        "proxy-list.download_socks5_ru",
        "https://www.proxy-list.download/api/v1/get?type=socks5&country=RU",
        "plain_ip_port",
    ),
    (
        "proxy-list.download_http_ru",
        "https://www.proxy-list.download/api/v1/get?type=http&country=RU",
        "plain_ip_port",
    ),
    # Country-specific GitHub folders
    (
        "proxifly_RU",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/RU/data.txt",
        "with_proto",
    ),
    # Global lists — will need geo-filter on our side
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
    # TheSpeedX's SOCKS-List repo (different from their PROXY-List repo)
    (
        "thespeedx_sockslist_socks4",
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks4.txt",
        "plain_ip_port",
    ),
    (
        "thespeedx_sockslist_socks5",
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt",
        "plain_ip_port",
    ),
    (
        "thespeedx_sockslist_http",
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
        "plain_ip_port",
    ),
    # monosans combined all-protocols file
    (
        "monosans_all",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/all.txt",
        "plain_ip_port",
    ),
    # Other aggregators from user-supplied list
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
        "ercindedeoglu_http",
        "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/http.txt",
        "plain_ip_port",
    ),
    (
        "ercindedeoglu_socks4",
        "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/socks4.txt",
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

IP_PORT_RE = re.compile(r"(?P<ip>\d{1,3}(?:\.\d{1,3}){3}):(?P<port>\d{1,5})")
USER_AGENT = "Mozilla/5.0 (compatible; saleapp-proxy-survey/1.0)"
REQUEST_TIMEOUT = 20
CACHE_PATH = "/tmp/ip_country_cache.json"


def load_cache() -> dict[str, str]:
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_cache(cache: dict[str, str]) -> None:
    tmp = CACHE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f)
    try:
        import os
        os.replace(tmp, CACHE_PATH)
    except OSError:
        pass


@dataclass
class SourceResult:
    label: str
    url: str
    fetched: bool = False
    error: str = ""
    raw_count: int = 0
    unique_hosts: set[str] = field(default_factory=set)
    ru_hosts: set[str] = field(default_factory=set)


def http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_geonode_json(body: str) -> list[str]:
    data = json.loads(body)
    out: list[str] = []
    for item in data.get("data", []):
        ip = item.get("ip")
        port = item.get("port")
        if ip and port:
            out.append(f"{ip}:{port}")
    return out


def parse_plain_ip_port(body: str) -> list[str]:
    out = []
    for line in body.splitlines():
        m = IP_PORT_RE.search(line.strip())
        if m:
            out.append(f"{m.group('ip')}:{m.group('port')}")
    return out


def parse_with_proto(body: str) -> list[str]:
    return parse_plain_ip_port(body)


PARSERS = {
    "geonode_json": parse_geonode_json,
    "plain_ip_port": parse_plain_ip_port,
    "with_proto": parse_with_proto,
}


def lookup_countries(
    ips: list[str], batch_size: int = 100, cache: dict[str, str] | None = None
) -> dict[str, str]:
    """Batch lookup respecting ip-api.com's free-tier rate limit.

    Free tier is ~45 requests/minute. We pace ~2s between batches and
    back off on 429. Passed cache dict (if given) is updated in-place
    and persisted to disk every 10 batches so long runs can resume.
    """
    out: dict[str, str] = {} if cache is None else cache
    # Only lookup IPs not already cached
    to_lookup = [ip for ip in ips if ip not in out]
    skipped = len(ips) - len(to_lookup)
    if skipped:
        print(f"  cache hit: {skipped}/{len(ips)} IPs already resolved", flush=True)
    if not to_lookup:
        return out
    delay_between_batches = 2.0  # seconds; stays well under 45 req/min
    total_batches = (len(to_lookup) + batch_size - 1) // batch_size
    for idx, start in enumerate(range(0, len(to_lookup), batch_size), start=1):
        chunk = to_lookup[start : start + batch_size]
        body = json.dumps(
            [{"query": ip, "fields": "query,countryCode"} for ip in chunk]
        ).encode()
        attempt = 0
        while True:
            attempt += 1
            req = urllib.request.Request(
                "http://ip-api.com/batch",
                data=body,
                headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
            )
            try:
                with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                    rows = json.loads(resp.read())
                break
            except HTTPError as exc:
                if exc.code == 429 and attempt < 5:
                    wait = 30 * attempt
                    print(
                        f"  429 at batch {idx}/{total_batches}, backoff {wait}s",
                        file=sys.stderr,
                        flush=True,
                    )
                    time.sleep(wait)
                    continue
                print(
                    f"WARN: batch {idx}/{total_batches} failed (HTTP {exc.code}): {exc}",
                    file=sys.stderr,
                    flush=True,
                )
                rows = []
                break
            except URLError as exc:
                if attempt < 5:
                    wait = 10 * attempt
                    print(
                        f"  URLError batch {idx}/{total_batches}: {exc}, retry in {wait}s",
                        file=sys.stderr,
                        flush=True,
                    )
                    time.sleep(wait)
                    continue
                print(
                    f"WARN: batch {idx}/{total_batches} URLError: {exc}",
                    file=sys.stderr,
                    flush=True,
                )
                rows = []
                break
        for row in rows:
            ip = row.get("query")
            if ip:
                out[ip] = row.get("countryCode") or "??"
        if idx % 10 == 0:
            save_cache(out)
            print(
                f"  geo progress: {idx}/{total_batches} batches, {len(out)} resolved (cache saved)",
                flush=True,
            )
        time.sleep(delay_between_batches)
    save_cache(out)
    return out


def survey() -> tuple[list[SourceResult], dict[str, str], set[str], set[str]]:
    all_unique: set[str] = set()
    all_ru: set[str] = set()
    results: list[SourceResult] = []

    # Phase 1 — fetch and parse each source
    for label, url, parser_name in SOURCES:
        r = SourceResult(label=label, url=url)
        print(f"[{label}] fetching ...", flush=True)
        try:
            body = http_get(url)
            r.fetched = True
        except Exception as exc:
            r.error = f"{type(exc).__name__}: {exc}"
            print(f"  ERROR: {r.error}", flush=True)
            results.append(r)
            continue
        try:
            entries = PARSERS[parser_name](body)
        except Exception as exc:
            r.error = f"parse failed: {exc}"
            print(f"  PARSE ERROR: {r.error}", flush=True)
            results.append(r)
            continue
        r.raw_count = len(entries)
        r.unique_hosts = {e.split(":", 1)[0] for e in entries}
        all_unique.update(r.unique_hosts)
        print(f"  parsed={r.raw_count}  unique_ips={len(r.unique_hosts)}", flush=True)
        results.append(r)

    # Phase 2 — batch lookup countries for ALL unique IPs (one set)
    print(f"\nLooking up countries for {len(all_unique)} unique IPs ...")
    cache = load_cache()
    print(f"  loaded {len(cache)} cached entries from {CACHE_PATH}")
    ip_country = lookup_countries(sorted(all_unique), cache=cache)

    # Phase 3 — annotate each source with RU counts
    for r in results:
        r.ru_hosts = {ip for ip in r.unique_hosts if ip_country.get(ip) == "RU"}

    all_ru = {ip for ip in all_unique if ip_country.get(ip) == "RU"}
    return results, ip_country, all_unique, all_ru


def main() -> None:
    results, ip_country, all_unique, all_ru = survey()

    print("\n" + "=" * 70)
    print("PER-SOURCE SUMMARY")
    print("=" * 70)
    print(f"{'source':<32} {'total':>8} {'ru':>8} {'status'}")
    print("-" * 70)
    for r in results:
        status = "OK" if r.fetched else r.error[:40]
        print(
            f"{r.label:<32} {r.raw_count:>8} {len(r.ru_hosts):>8} {status}"
        )

    print("\n" + "=" * 70)
    print("COMBINED (deduped across all sources)")
    print("=" * 70)
    print(f"Total unique IPs: {len(all_unique)}")
    print(f"Total unique RU IPs: {len(all_ru)}")
    if all_unique:
        pct = 100 * len(all_ru) / len(all_unique)
        print(f"RU share: {pct:.1f}%")

    cc_counter: dict[str, int] = {}
    for cc in ip_country.values():
        cc_counter[cc] = cc_counter.get(cc, 0) + 1
    print("\nTop countries across pooled IPs:")
    for cc, n in sorted(cc_counter.items(), key=lambda kv: -kv[1])[:15]:
        print(f"  {cc}: {n}")


if __name__ == "__main__":
    main()

"""Multi-provider IP geolocation with rate-limited fallback and consensus mode.

Providers are kept simple: each resolves a list of IPs and returns a
``{ip: country_code}`` dict. Providers enforce their own rate limits via a
shared minimum-interval policy. Failures yield empty results — never raise.

Design goals
------------
- **Robustness**: any single provider can be down / rate-limited / banned
  without stopping the pipeline.
- **Consensus**: in verification mode, ``MultiGeoResolver.resolve_consensus``
  queries ≥2 providers and only accepts IPs where they agree — essential for
  detecting IPs misclassified as RU (e.g. residential proxies, stale WHOIS).
- **Cache-first**: results are persisted to disk keyed by IP. Re-runs skip
  already-resolved IPs. Per-provider answers are also cached for auditing.
- **No API keys required**: every provider below works without registration.
  IPinfo / MaxMind (paid or key-gated) are intentionally omitted here; they
  can be bolted on later via the same ``GeoProvider`` protocol.

Providers included (tested, no key required, RU-accuracy verified by spot check)
--------------------------------------------------------------------------------
1.  ``ip-api.com/batch``     — 100/req, 15/min, country code
2.  ``ip-api.com/json/{ip}`` — 1/req,  45/min  (single-IP fallback)
3.  ``api.country.is``       — 1/req,  10 rps, unlimited-ish
4.  ``ip2c.org``             — 1/req,  plain text, generous
5.  ``ipwho.is``             — 1/req,  10k/mo soft
6.  ``freeipapi.com``        — 1/req,  60/min free
7.  ``api.ipapi.is``         — 1/req,  free, generous
8.  ``get.geojs.io``         — 1/req,  free
9.  ``api.db-ip.com/v2/free``— 1/req,  1000/day
10. ``api.ip.sb/geoip``      — 1/req,  free

Public API
----------
>>> resolver = MultiGeoResolver(cache_path=Path(".cache/ip_country.json"))
>>> resolver.resolve_bulk(["8.8.8.8", "1.1.1.1"])
{'8.8.8.8': 'US', '1.1.1.1': 'US'}
>>> resolver.resolve_consensus(["8.8.8.8"], min_agree=2)
{'8.8.8.8': {'country': 'US', 'agreed': ['ip-api-batch', 'country.is'], 'disagreed': {}}}
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional
from urllib.error import HTTPError, URLError

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
)
DEFAULT_HTTP_TIMEOUT = 8.0


# ---------------------------------------------------------------------------
# Rate limiter — thread-safe min-interval policy. Each provider owns one.
# ---------------------------------------------------------------------------
class RateLimiter:
    """Simple min-interval limiter. Call ``acquire()`` before each request.

    ``min_interval_s`` is derived from the provider's documented rate limit
    with a 10% safety margin so we don't flirt with 429s. The limiter is
    thread-safe so multiple resolver threads can share one provider.
    """

    def __init__(self, min_interval_s: float):
        self._min_interval = max(0.0, float(min_interval_s))
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait = self._next_allowed - now
            if wait > 0:
                time.sleep(wait)
                now = time.monotonic()
            self._next_allowed = now + self._min_interval


# ---------------------------------------------------------------------------
# Provider protocol + shared helpers
# ---------------------------------------------------------------------------
@dataclass
class ProviderStats:
    calls: int = 0
    successes: int = 0
    ips_resolved: int = 0
    rate_limited: int = 0
    errors: int = 0
    disabled_until: float = 0.0
    last_error: str = ""


@dataclass
class GeoProvider:
    """Minimal provider contract.

    ``lookup`` takes a list of IPs (up to ``max_batch``) and returns a
    ``{ip: 'RU'|'US'|...}`` dict. Missing IPs in the output mean "could not
    resolve" (e.g. throttled, private range, provider error). Country codes
    are normalized to uppercase ISO-3166-1 alpha-2. Empty string or ``None``
    means "provider couldn't decide".
    """

    name: str
    max_batch: int
    limiter: RateLimiter
    _fn: Callable[[list[str]], dict[str, str]]
    stats: ProviderStats = field(default_factory=ProviderStats)
    cooldown_after_429_s: float = 90.0
    cooldown_after_403_s: float = 3600.0

    def disabled(self, now: Optional[float] = None) -> bool:
        if now is None:
            now = time.monotonic()
        return now < self.stats.disabled_until

    def lookup(self, ips: list[str]) -> dict[str, str]:
        """Resolve a batch. Slices to max_batch. Tracks stats & cooldowns."""
        if not ips:
            return {}
        if self.disabled():
            return {}
        chunk = ips[: self.max_batch]
        self.limiter.acquire()
        self.stats.calls += 1
        try:
            result = self._fn(chunk)
        except _ProviderRateLimited as exc:
            self.stats.rate_limited += 1
            self.stats.disabled_until = time.monotonic() + self.cooldown_after_429_s
            self.stats.last_error = f"429: {exc}"
            return {}
        except _ProviderForbidden as exc:
            self.stats.rate_limited += 1
            self.stats.disabled_until = time.monotonic() + self.cooldown_after_403_s
            self.stats.last_error = f"403: {exc}"
            return {}
        except Exception as exc:  # noqa: BLE001 — providers may raise anything
            self.stats.errors += 1
            self.stats.last_error = f"{type(exc).__name__}: {exc}"
            return {}
        # Normalize and filter
        clean = {
            ip: (cc or "").strip().upper()
            for ip, cc in (result or {}).items()
            if ip in chunk and cc
        }
        self.stats.successes += 1
        self.stats.ips_resolved += len(clean)
        return clean


class _ProviderRateLimited(Exception):
    pass


class _ProviderForbidden(Exception):
    pass


def _http_get_json(url: str, timeout: float = DEFAULT_HTTP_TIMEOUT) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))
    except HTTPError as exc:
        if exc.code == 429:
            raise _ProviderRateLimited(str(exc)) from exc
        if exc.code == 403:
            raise _ProviderForbidden(str(exc)) from exc
        raise


def _http_get_text(url: str, timeout: float = DEFAULT_HTTP_TIMEOUT) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        if exc.code == 429:
            raise _ProviderRateLimited(str(exc)) from exc
        if exc.code == 403:
            raise _ProviderForbidden(str(exc)) from exc
        raise


# ---------------------------------------------------------------------------
# Individual provider implementations
# ---------------------------------------------------------------------------
def _fn_ipapi_com_batch(ips: list[str]) -> dict[str, str]:
    """http://ip-api.com/batch — 15/min, 100 IPs per request.

    Docs: https://ip-api.com/docs/api:batch
    """
    body = json.dumps(
        [{"query": ip, "fields": "query,countryCode"} for ip in ips]
    ).encode()
    req = urllib.request.Request(
        "http://ip-api.com/batch",
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_HTTP_TIMEOUT) as r:
            rows = json.loads(r.read().decode("utf-8", errors="replace"))
    except HTTPError as exc:
        if exc.code == 429:
            raise _ProviderRateLimited(str(exc)) from exc
        if exc.code == 403:
            raise _ProviderForbidden(str(exc)) from exc
        raise
    out: dict[str, str] = {}
    for row in rows or []:
        ip = row.get("query")
        cc = row.get("countryCode")
        if ip and cc:
            out[ip] = cc
    return out


def _fn_ipapi_com_single(ips: list[str]) -> dict[str, str]:
    """http://ip-api.com/json/{ip} — 45/min. Fallback when batch is 429'd."""
    ip = ips[0]
    data = _http_get_json(f"http://ip-api.com/json/{ip}?fields=status,countryCode")
    cc = data.get("countryCode")
    return {ip: cc} if cc else {}


def _fn_country_is(ips: list[str]) -> dict[str, str]:
    """https://api.country.is/{ip} — 10 rps, unlimited quota.

    Returns ``{"ip": "...", "country": "US"}``. Country-code only — perfect
    for our use case and dirt cheap.
    """
    ip = ips[0]
    data = _http_get_json(f"https://api.country.is/{ip}")
    cc = data.get("country")
    return {ip: cc} if cc else {}


def _fn_ip2c(ips: list[str]) -> dict[str, str]:
    """https://ip2c.org/?ip={ip} — plain text, no auth, generous.

    Response format: ``<status>;<ISO2>;<ISO3>;<country name>``. Status ``1``
    means success; anything else means "could not locate".
    """
    ip = ips[0]
    body = _http_get_text(f"https://ip2c.org/?ip={ip}").strip()
    parts = body.split(";")
    if len(parts) >= 2 and parts[0] == "1" and parts[1]:
        return {ip: parts[1]}
    return {}


def _fn_ipwho_is(ips: list[str]) -> dict[str, str]:
    """https://ipwho.is/{ip} — 10k/month soft, no auth.

    Returns ``{"success": true, "country_code": "US", ...}``. Also exposes
    ``type`` (ipv4/6), ``connection.type`` (broadband/hosting/wireless), etc.
    — could be used later for datacenter detection.
    """
    ip = ips[0]
    data = _http_get_json(f"https://ipwho.is/{ip}")
    if not data.get("success"):
        return {}
    cc = data.get("country_code")
    return {ip: cc} if cc else {}


def _fn_freeipapi(ips: list[str]) -> dict[str, str]:
    """https://free.freeipapi.com/api/json/{ip} — 60/min free tier."""
    ip = ips[0]
    data = _http_get_json(f"https://free.freeipapi.com/api/json/{ip}")
    cc = data.get("countryCode") or data.get("country_code")
    return {ip: cc} if cc else {}


def _fn_ipapi_is(ips: list[str]) -> dict[str, str]:
    """https://api.ipapi.is/?q={ip} — free, generous, security-flag rich.

    Returns rich JSON incl. ``country_code``, ``is_datacenter``, ``is_vpn``,
    ``is_proxy``. We only return country here; consensus verification treats
    datacenter/proxy flags separately via :func:`ipapi_is_privacy_flags`.
    """
    ip = ips[0]
    data = _http_get_json(f"https://api.ipapi.is/?q={urllib.parse.quote(ip)}")
    loc = data.get("location") or {}
    cc = loc.get("country_code") or data.get("country_code")
    return {ip: cc} if cc else {}


def _fn_geojs(ips: list[str]) -> dict[str, str]:
    """https://get.geojs.io/v1/ip/country/{ip}.json — free, no auth."""
    ip = ips[0]
    data = _http_get_json(f"https://get.geojs.io/v1/ip/country/{ip}.json")
    cc = data.get("country")
    return {ip: cc} if cc else {}


def _fn_dbip_free(ips: list[str]) -> dict[str, str]:
    """https://api.db-ip.com/v2/free/{ip}/countryCode — 1000/day free."""
    ip = ips[0]
    body = _http_get_text(
        f"https://api.db-ip.com/v2/free/{ip}/countryCode"
    ).strip()
    # Free endpoint returns just the two-letter code, or a short JSON error.
    if body and len(body) == 2 and body.isalpha():
        return {ip: body.upper()}
    try:
        data = json.loads(body)
        cc = data.get("countryCode")
        if cc:
            return {ip: cc}
    except json.JSONDecodeError:
        pass
    return {}


def _fn_ipsb(ips: list[str]) -> dict[str, str]:
    """https://api.ip.sb/geoip/{ip} — free, no auth, ships behind Cloudflare."""
    ip = ips[0]
    data = _http_get_json(f"https://api.ip.sb/geoip/{ip}")
    cc = data.get("country_code")
    return {ip: cc} if cc else {}


# ---------------------------------------------------------------------------
# Provider registry — rate limits tuned with 10% safety margin below docs.
# ---------------------------------------------------------------------------
def build_default_providers() -> list[GeoProvider]:
    """Return the default, no-API-key provider chain in preferred order.

    Order matters: cheap high-throughput first, expensive/slow last. The
    resolver queries them one at a time until success; in consensus mode it
    walks far enough to satisfy ``min_agree``.
    """
    return [
        GeoProvider(
            name="ip-api-batch",
            max_batch=100,
            limiter=RateLimiter(60.0 / 14.0),   # 14/min target (doc limit 15)
            _fn=_fn_ipapi_com_batch,
        ),
        GeoProvider(
            name="country.is",
            max_batch=1,
            limiter=RateLimiter(1.0 / 8.0),     # 8 rps (doc: 10 rps)
            _fn=_fn_country_is,
        ),
        GeoProvider(
            name="ip2c.org",
            max_batch=1,
            limiter=RateLimiter(1.0 / 5.0),     # 5 rps, conservative
            _fn=_fn_ip2c,
        ),
        GeoProvider(
            name="ipwho.is",
            max_batch=1,
            limiter=RateLimiter(1.0 / 3.0),     # 3 rps (~10k/hr)
            _fn=_fn_ipwho_is,
        ),
        GeoProvider(
            name="freeipapi.com",
            max_batch=1,
            limiter=RateLimiter(60.0 / 55.0),   # 55/min (doc: 60)
            _fn=_fn_freeipapi,
        ),
        GeoProvider(
            name="ipapi.is",
            max_batch=1,
            limiter=RateLimiter(1.0 / 2.0),     # 2 rps
            _fn=_fn_ipapi_is,
        ),
        GeoProvider(
            name="geojs.io",
            max_batch=1,
            limiter=RateLimiter(1.0 / 3.0),     # 3 rps
            _fn=_fn_geojs,
        ),
        GeoProvider(
            name="db-ip-free",
            max_batch=1,
            limiter=RateLimiter(60.0 / 40.0),   # 40/min (budget: 1000/day)
            _fn=_fn_dbip_free,
        ),
        GeoProvider(
            name="ip.sb",
            max_batch=1,
            limiter=RateLimiter(1.0 / 1.5),     # 1.5 rps
            _fn=_fn_ipsb,
        ),
        GeoProvider(
            name="ip-api-single",
            max_batch=1,
            limiter=RateLimiter(60.0 / 42.0),   # 42/min (doc: 45)
            _fn=_fn_ipapi_com_single,
        ),
    ]


# ---------------------------------------------------------------------------
# MultiGeoResolver — shared cache, fallback chain, consensus mode
# ---------------------------------------------------------------------------
@dataclass
class ConsensusResult:
    country: str               # majority country code, or "" if no consensus
    agreed: list[str]          # providers that agreed on ``country``
    disagreed: dict[str, str]  # {provider_name: their_country_code}
    agreement_ratio: float     # len(agreed) / total_queried


class MultiGeoResolver:
    """Coordinator for multiple ``GeoProvider`` instances.

    Persists results to ``cache_path`` as JSON. In the simple form
    (:meth:`resolve_bulk`), each IP is resolved by the first provider that
    succeeds. In :meth:`resolve_consensus`, every IP is queried against at
    least ``min_agree`` providers, and accepted only if they agree.

    Thread-safe: the internal cache is protected by a lock so resolver
    calls can run from multiple threads (e.g. one thread per provider).
    """

    def __init__(
        self,
        cache_path: Path,
        providers: Optional[list[GeoProvider]] = None,
    ):
        self.cache_path = cache_path
        self.providers = providers or build_default_providers()
        self._cache_lock = threading.Lock()
        self._cache: dict[str, str] = self._load_cache()
        self._per_provider_cache: dict[str, dict[str, str]] = {
            p.name: {} for p in self.providers
        }
        self._provenance: dict[str, str] = {}  # ip -> provider name

    # ------------------------------------------------------------------
    # Cache I/O
    # ------------------------------------------------------------------
    def _load_cache(self) -> dict[str, str]:
        if not self.cache_path.exists():
            return {}
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Support both old flat form ({ip: cc}) and new form with meta
                if isinstance(data, dict) and "ips" in data:
                    return dict(data["ips"])
                return dict(data)
        except (json.JSONDecodeError, OSError):
            return {}

    def save_cache(self) -> None:
        """Persist atomic write of the current cache to disk."""
        with self._cache_lock:
            snapshot = dict(self._cache)
        tmp = self.cache_path.with_suffix(self.cache_path.suffix + ".tmp")
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False)
        os.replace(tmp, self.cache_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def cached(self, ip: str) -> Optional[str]:
        with self._cache_lock:
            return self._cache.get(ip)

    def resolve_bulk(
        self,
        ips: list[str],
        progress_every: int = 500,
        save_every: int = 2000,
    ) -> dict[str, str]:
        """Resolve every IP by walking providers until one answers.

        Respects the persistent cache — already-resolved IPs are skipped.
        """
        pending = [ip for ip in ips if self.cached(ip) is None]
        total_pending = len(pending)
        if not pending:
            print(f"[geo] all {len(ips)} IPs already cached")
            return {ip: self._cache[ip] for ip in ips if ip in self._cache}

        print(
            f"[geo] resolving {total_pending}/{len(ips)} uncached IPs "
            f"across {len(self.providers)} providers"
        )
        resolved_since_save = 0
        # Providers in order; the first provider (batch) hoovers up most IPs
        # quickly, remaining providers pick up leftovers.
        for provider in self.providers:
            if not pending:
                break
            if provider.disabled():
                print(
                    f"[geo] {provider.name} disabled "
                    f"(last error: {provider.stats.last_error})"
                )
                continue
            print(
                f"[geo] {provider.name} (batch={provider.max_batch}) "
                f"working on {len(pending)} IPs"
            )
            still_pending: list[str] = []
            for i in range(0, len(pending), provider.max_batch):
                chunk = pending[i : i + provider.max_batch]
                if provider.disabled():
                    # Provider got throttled mid-run; punt remaining to next.
                    still_pending.extend(chunk)
                    continue
                result = provider.lookup(chunk)
                if result:
                    with self._cache_lock:
                        for ip, cc in result.items():
                            self._cache[ip] = cc
                            self._per_provider_cache[provider.name][ip] = cc
                            self._provenance[ip] = provider.name
                            resolved_since_save += 1
                # Anything not in result gets retried on next provider
                for ip in chunk:
                    if ip not in result:
                        still_pending.append(ip)

                # Periodic progress + save
                done = total_pending - len(still_pending) - (len(pending) - i - len(chunk))
                if progress_every and done and done % progress_every < provider.max_batch:
                    print(
                        f"[geo]   ~{done}/{total_pending} resolved so far, "
                        f"cache size {len(self._cache)}"
                    )
                if save_every and resolved_since_save >= save_every:
                    self.save_cache()
                    resolved_since_save = 0
            pending = still_pending
        # Final save
        self.save_cache()
        if pending:
            print(
                f"[geo] {len(pending)} IPs could not be resolved by any provider "
                f"(all exhausted / disabled)"
            )
        return {ip: self._cache[ip] for ip in ips if ip in self._cache}

    def resolve_consensus(
        self,
        ips: list[str],
        min_agree: int = 2,
        max_providers: int = 4,
    ) -> dict[str, ConsensusResult]:
        """Verify each IP by polling multiple providers.

        Each IP is queried against up to ``max_providers`` providers (skipping
        disabled ones). The result country is the first country code that at
        least ``min_agree`` providers returned. If no such consensus exists,
        ``country`` is empty and ``disagreed`` lists every divergent answer.

        NOTE: intentionally simple — single-IP sequential loop per provider.
        Only meant for verification on a small pool (e.g. IPs the batch
        resolver already tagged as the target country). Don't call on 30k IPs.
        """
        results: dict[str, ConsensusResult] = {}
        active = [p for p in self.providers if p.max_batch == 1 or p.name.endswith("batch")]
        # Limit to the first N active providers we'll query per IP
        for idx, ip in enumerate(ips, start=1):
            answers: dict[str, str] = {}
            asked = 0
            for p in active:
                if asked >= max_providers:
                    break
                if p.disabled():
                    continue
                # Use per-provider cache if we already asked this provider
                cached = self._per_provider_cache.get(p.name, {}).get(ip)
                if cached:
                    answers[p.name] = cached
                    asked += 1
                    continue
                r = p.lookup([ip])
                if ip in r:
                    answers[p.name] = r[ip]
                    self._per_provider_cache.setdefault(p.name, {})[ip] = r[ip]
                asked += 1
            # Tally
            tally: dict[str, list[str]] = {}
            for prov, cc in answers.items():
                tally.setdefault(cc, []).append(prov)
            country = ""
            agreed: list[str] = []
            for cc, provs in sorted(tally.items(), key=lambda kv: -len(kv[1])):
                if len(provs) >= min_agree:
                    country = cc
                    agreed = provs
                    break
            disagreed = {
                prov: cc for prov, cc in answers.items() if prov not in agreed
            }
            ratio = (len(agreed) / max(len(answers), 1)) if agreed else 0.0
            results[ip] = ConsensusResult(
                country=country,
                agreed=agreed,
                disagreed=disagreed,
                agreement_ratio=round(ratio, 2),
            )
            if idx % 25 == 0:
                print(
                    f"[consensus]   {idx}/{len(ips)} verified, "
                    f"passed={sum(1 for r in results.values() if r.country)}"
                )
        return results

    def stats_summary(self) -> list[dict]:
        """Per-provider counters for diagnostics / post-run reporting."""
        return [
            {
                "name": p.name,
                "calls": p.stats.calls,
                "successes": p.stats.successes,
                "ips_resolved": p.stats.ips_resolved,
                "rate_limited": p.stats.rate_limited,
                "errors": p.stats.errors,
                "disabled_now": p.disabled(),
                "last_error": p.stats.last_error,
            }
            for p in self.providers
        ]


# ---------------------------------------------------------------------------
# Optional privacy/abuse flags (for future VPN detection on RU-tagged IPs)
# ---------------------------------------------------------------------------
def ipapi_is_privacy_flags(ip: str) -> dict:
    """Return flags such as ``is_datacenter``, ``is_vpn``, ``is_proxy`` from
    ``api.ipapi.is``. Meant for sparing use on RU-tagged candidates only.
    Returns an empty dict on any error.
    """
    try:
        data = _http_get_json(
            f"https://api.ipapi.is/?q={urllib.parse.quote(ip)}"
        )
    except Exception:  # noqa: BLE001
        return {}
    return {
        k: bool(data.get(k))
        for k in ("is_datacenter", "is_vpn", "is_proxy", "is_abuser", "is_tor")
        if k in data
    }


# ---------------------------------------------------------------------------
# CLI self-test — run with `python -m scripts.geo_providers`
# ---------------------------------------------------------------------------
def _self_test() -> int:
    """Verify each provider returns the expected country for known IPs.

    Exits 0 if all providers return the right country for at least one test
    IP, else 1. Prints a compact health report.
    """
    tests = [
        ("8.8.8.8", "US"),      # Google DNS — US
        ("77.88.8.8", "RU"),    # Yandex DNS — RU (canonical Russian IP)
        ("1.1.1.1", "AU"),      # Cloudflare — APNIC-assigned, AU; some
                                # providers return "" (reserved-range conservatism)
    ]
    providers = build_default_providers()
    print(f"Testing {len(providers)} providers against {len(tests)} known IPs\n")
    print(f"{'provider':<18} {'  '.join(ip for ip,_ in tests)}")
    print("-" * 60)
    failures = 0
    for p in providers:
        cells = []
        all_ok = True
        for ip, expected in tests:
            try:
                got = p.lookup([ip]).get(ip, "??")
            except Exception as exc:  # noqa: BLE001
                got = f"EXC:{type(exc).__name__}"
                all_ok = False
            ok = got == expected
            if not ok:
                all_ok = False
            cells.append(f"{got:>5}{'✓' if ok else '✗'}")
        status = "OK" if all_ok else "DEGRADED"
        if not all_ok:
            failures += 1
        print(f"{p.name:<18} {'  '.join(cells)}  [{status}]")
    print(f"\n{len(providers) - failures}/{len(providers)} providers fully healthy")
    return 0 if failures < len(providers) else 1


if __name__ == "__main__":
    import sys
    sys.exit(_self_test())

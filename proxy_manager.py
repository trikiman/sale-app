"""
Proxy Manager for VkusVill scrapers.

Fetches SOCKS5 proxies from proxifly public list, tests them against VkusVill,
caches working proxies, and provides rotation when direct connection is blocked.

Usage:
    from proxy_manager import ProxyManager
    pm = ProxyManager()
    if not pm.check_direct():
        proxy = pm.get_working_proxy()  # "ip:port" or None
"""
import json
import os
import socket
import time
import concurrent.futures
from datetime import datetime

# Try httpx first (already used by scrapers), fallback to basic sockets
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CACHE_FILE = os.path.join(DATA_DIR, "working_proxies.json")
EVENTS_FILE = os.path.join(DATA_DIR, "proxy_events.jsonl")

# SOCKS5 proxy list (proxifly has ~43% success rate for VkusVill)
SOCKS5_LIST_URLS = [
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/refs/heads/main/proxies/all/data.txt",
]

# How many proxies to keep in cache
MAX_CACHED = 30
# Minimum healthy proxies — triggers refresh if pool drops below this
MIN_HEALTHY = 7
# Concurrent test workers (SSL handshakes are CPU-heavy, keep moderate)
TEST_WORKERS = 30
# Timeout for each proxy test (seconds)
TEST_TIMEOUT = 10
# Cache validity (seconds) — refresh if older than 24h regardless
CACHE_TTL = 86400  # 24 hours
# VkusVill probe timeout
PROBE_TIMEOUT = 8
DIRECT_CHECK_TTL = 60
# SOCKS5 preflight timeouts (kernel-level, always honored). Keeps dead proxies
# from reaching the httpx layer, where SOCKS recv() may hang indefinitely.
SOCKS5_CONNECT_TIMEOUT = 3.0
SOCKS5_HANDSHAKE_TIMEOUT = 2.0
# Hard outer ceiling for refresh_proxy_list — main thread never blocks past this.
REFRESH_OUTER_TIMEOUT_SLACK = 15.0

VKUSVILL_URL = "https://vkusvill.ru/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"


class ProxyManager:
    def __init__(self, log_func=None):
        self._log = log_func or (lambda msg: print(f"  [PROXY] {msg}"))
        self._cache = self._load_cache()
        self._direct_check = {"checked_at": 0.0, "ok": None}

    def _track_event(self, event_type: str, data: dict | None = None):
        """Append a proxy event to the JSONL log for historical stats."""
        entry = {
            "ts": datetime.now().isoformat(),
            "event": event_type,
        }
        if data:
            entry.update(data)
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(EVENTS_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass  # Don't crash on stats write failure

    # ── Public API ──────────────────────────────────────────────

    def check_direct(self) -> bool:
        """Check if VkusVill is reachable WITHOUT a proxy (direct IP)."""
        return self._probe_vkusvill(proxy=None)

    def note_direct_result(self, ok: bool):
        """Update cached direct-connectivity result after a live request attempt."""
        self._direct_check = {"checked_at": time.time(), "ok": bool(ok)}

    def check_direct_cached(self, ttl: int = DIRECT_CHECK_TTL) -> bool:
        """Use a short-lived cache so hot paths do not probe direct connectivity every call."""
        cached_ok = self._direct_check.get("ok")
        checked_at = self._direct_check.get("checked_at", 0.0)
        if cached_ok is not None and (time.time() - checked_at) < ttl:
            return bool(cached_ok)

        ok = self.check_direct()
        self.note_direct_result(ok)
        return ok

    def get_working_proxy(self, allow_refresh: bool = True) -> str | None:
        """Get a SOCKS5 proxy for VkusVill. Returns 'ip:port' or None.

        If cache has proxies → return first one instantly (no re-testing).
        If cache empty → fetch fresh list, test, cache, return best.
        """
        if allow_refresh:
            self.ensure_pool()  # auto-refresh if pool is low
        proxies = self._cache.get("proxies", [])

        if proxies:
            addr = proxies[0]["addr"]
            self._log(f"Using cached proxy: {addr} ({len(proxies)} in pool)")
            return addr

        self._log("No working proxies found!")
        return None

    def get_proxy_for_chrome(self) -> str | None:
        """Returns full socks5://ip:port string for Chrome --proxy-server flag."""
        proxy = self.get_working_proxy()
        if proxy:
            return f"socks5://{proxy}"
        return None

    def pool_count(self) -> int:
        """Number of proxies currently in pool."""
        return len(self._cache.get("proxies", []))

    def pool_healthy(self) -> bool:
        """True if pool has enough proxies (>= MIN_HEALTHY)."""
        return self.pool_count() >= MIN_HEALTHY

    def remove_proxy(self, addr: str) -> None:
        """Remove a dead proxy from pool (e.g. after scraper failure).
        If pool drops below MIN_HEALTHY, next get_working_proxy() auto-refreshes.
        """
        proxies = self._cache.get("proxies", [])
        before = len(proxies)
        self._cache["proxies"] = [p for p in proxies if p["addr"] != addr]
        after = len(self._cache["proxies"])
        if before != after:
            self._save_cache()
            self._log(f"Removed dead proxy {addr} ({after} remaining in pool)")
            self._track_event("removed", {"addr": addr, "pool_after": after})
        if after < MIN_HEALTHY:
            self._log(f"Pool below {MIN_HEALTHY} — will refresh on next use")

    def next_proxy(self) -> str | None:
        """Remove current (first) proxy and return the next one.
        Used for rotation after a proxy fails.
        """
        proxies = self._cache.get("proxies", [])
        if proxies:
            dead = proxies[0]["addr"]
            self.remove_proxy(dead)
        return self.get_working_proxy()

    def ensure_pool(self) -> int:
        """Ensure pool has >= MIN_HEALTHY proxies. Refresh if not.
        Also refreshes if cache is stale (> 24h).
        Returns current pool count.
        """
        count = self.pool_count()
        stale = self.is_cache_stale()

        if count >= MIN_HEALTHY and not stale:
            return count

        if stale:
            self._log(f"Daily refresh (cache > {CACHE_TTL//3600}h old)")
        else:
            self._log(f"Pool low ({count}/{MIN_HEALTHY}) — refreshing...")

        # Keep existing good proxies, add new ones
        existing = {p["addr"] for p in self._cache.get("proxies", [])}
        self.refresh_proxy_list(exclude=existing)
        total = self.pool_count()
        self._log(f"Pool now has {total} proxies")
        return total

    def refresh_proxy_list(self, exclude: set[str] | None = None) -> int:
        """Fetch fresh SOCKS5 list, test against VkusVill, cache working ones.
        Args:
            exclude: set of proxy addrs to skip (already in pool)
        Returns number of NEW working proxies found.
        """
        self._log(f"Fetching SOCKS5 lists from {len(SOCKS5_LIST_URLS)} sources...")

        # Fetch the list
        try:
            proxies = self._fetch_proxy_list()
            self._log(f"Got {len(proxies)} SOCKS5 proxies")
        except Exception as e:
            self._log(f"Failed to fetch proxy list: {e}")
            return 0

        # Remove already-known proxies
        if exclude:
            proxies = [p for p in proxies if p not in exclude]
            self._log(f"  {len(proxies)} new (excluded {len(exclude)} existing)")

        # How many more do we need?
        existing = self._cache.get("proxies", [])
        need = MAX_CACHED - len(existing)
        if need <= 0:
            self._log(f"Pool already full ({len(existing)}/{MAX_CACHED})")
            return 0

        # Test proxies with early stop when enough found OR time/count limit hit
        max_tests = min(len(proxies), 300)  # don't grind through thousands
        max_time = 120  # 2 minute hard limit
        self._log(f"Testing up to {max_tests} proxies, need {need} more (limit: {max_time}s)...")

        working = []
        tested = 0
        start_time = time.time()
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=TEST_WORKERS)
        futures = {}
        pending = set()
        outer_timeout = max_time + REFRESH_OUTER_TIMEOUT_SLACK
        try:
            futures = {pool.submit(self._test_proxy, p): p for p in proxies[:max_tests]}
            pending = set(futures)
            try:
                for future in concurrent.futures.as_completed(futures, timeout=outer_timeout):
                    pending.discard(future)
                    tested += 1
                    try:
                        result = future.result()
                    except Exception as exc:
                        result = None
                        self._log(f"  probe error: {exc}")
                    if result:
                        addr, speed = result
                        working.append({"addr": addr, "speed": speed,
                                        "tested_at": datetime.now().isoformat()})
                        self._log(f"  ✓ {addr} ({speed:.1f}s) [{tested}/{max_tests}]")
                    elif tested % 100 == 0:
                        self._log(f"  ... {tested}/{max_tests} tested, {len(working)} good so far")
                    if len(working) >= need:
                        self._log(f"  Found {len(working)} new proxies, stopping.")
                        break
                    if time.time() - start_time > max_time:
                        self._log(f"  Time limit ({max_time}s) — got {len(working)} of {need} needed.")
                        break
            except concurrent.futures.TimeoutError:
                self._log(
                    f"  Outer timeout {outer_timeout:.0f}s hit — aborting with "
                    f"{len(working)} working, {tested} tested."
                )
        finally:
            for future in pending:
                future.cancel()
            # NEVER wait for probe workers. SOCKS5 recv() can hang in the kernel
            # beyond any Python-level timeout; wait=True would deadlock the main
            # thread. Cancelled-but-running threads exit on their own once their
            # socket times out; _socks5_preflight guarantees short tails.
            pool.shutdown(wait=False, cancel_futures=True)

        # Merge with existing pool
        existing = self._cache.get("proxies", [])
        existing_addrs = {p["addr"] for p in existing}
        for w in working:
            if w["addr"] not in existing_addrs:
                existing.append(w)

        # Subnet diversity: max 3 proxies per /24 subnet
        # Prevents all proxies from one datacenter (e.g. 206.123.156.x)
        MAX_PER_SUBNET = 3
        existing.sort(key=lambda p: p.get("speed", 999))
        diverse: list[dict] = []
        subnet_counts: dict[str, int] = {}
        for p in existing:
            subnet = '.'.join(p["addr"].split(':')[0].split('.')[:3])
            cnt = subnet_counts.get(subnet, 0)
            if cnt < MAX_PER_SUBNET:
                diverse.append(p)
                subnet_counts[subnet] = cnt + 1
            if len(diverse) >= MAX_CACHED:
                break

        self._cache = {
            "updated_at": datetime.now().isoformat(),
            "proxies": diverse,
        }
        self._save_cache()
        # Track the refresh event
        self._track_event("refresh", {
            "tested": tested,
            "found": len(working),
            "pool_size": len(diverse),
        })
        # Log subnet distribution
        if subnet_counts:
            dist = ', '.join(f"{s}:×{c}" for s, c in sorted(subnet_counts.items(), key=lambda x: -x[1])[:5])
            self._log(f"  Subnet diversity: {dist}")
        self._log(f"Cached {len(diverse)} working proxies (+{len(working)} new)")
        return len(working)

    def is_cache_stale(self) -> bool:
        """Check if proxy cache needs refresh."""
        updated = self._cache.get("updated_at")
        if not updated:
            return True
        try:
            updated_dt = datetime.fromisoformat(updated)
            age = (datetime.now() - updated_dt).total_seconds()
            return age > CACHE_TTL
        except:
            return True

    # ── Private helpers ─────────────────────────────────────────

    def _probe_vkusvill(self, proxy: str | None = None, verify_ssl: bool = False) -> bool:
        """Quick probe: can we reach VkusVill.ru?
        When testing proxies, verify_ssl=True rejects MITM proxies with fake certs.
        """
        if not HAS_HTTPX:
            return self._probe_vkusvill_urllib(proxy)
        try:
            kwargs = {
                "timeout": PROBE_TIMEOUT,
                "verify": verify_ssl,  # True for proxy tests → reject MITM
                "headers": {"User-Agent": UA},
                "follow_redirects": True,
            }
            if proxy:
                kwargs["proxy"] = f"socks5://{proxy}"
            with httpx.Client(**kwargs) as client:
                r = client.get(VKUSVILL_URL)
                if r.status_code != 200:
                    return False
                # Extra check: page content must contain VkusVill
                # (catches captcha pages, block pages, MITM injection)
                body = r.text[:5000].lower()
                return "vkusvill" in body
        except:
            return False

    def _probe_vkusvill_urllib(self, proxy: str | None = None) -> bool:
        """Fallback probe using urllib (no httpx)."""
        import urllib.request
        import ssl
        try:
            if proxy:
                handler = urllib.request.ProxyHandler({"https": f"socks5://{proxy}"})
                opener = urllib.request.build_opener(handler)
            else:
                opener = urllib.request.build_opener()
            req = urllib.request.Request(VKUSVILL_URL, headers={"User-Agent": UA})
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            r = opener.open(req, timeout=PROBE_TIMEOUT)
            return r.status == 200
        except:
            return False

    @staticmethod
    def _normalize_proxy(line: str) -> str | None:
        """Normalize proxy line to ip:port format.
        Handles: ip:port, socks5://ip:port, socks4://ip:port, http://ip:port
        """
        line = line.strip()
        if not line:
            return None
        # Strip protocol prefixes
        for prefix in ('socks5://', 'socks4://', 'http://', 'https://'):
            if line.lower().startswith(prefix):
                line = line[len(prefix):]
                break
        # Only keep socks5-compatible entries (ip:port)
        if ':' in line:
            return line
        return None

    def _fetch_proxy_list(self) -> list[str]:
        """Download SOCKS5 proxy lists from multiple sources, deduplicate."""
        all_proxies = set()
        for url in SOCKS5_LIST_URLS:
            src = url.split('/')[-2]  # short name for logging
            try:
                if HAS_HTTPX:
                    r = httpx.get(url, timeout=15)
                    r.raise_for_status()
                    text = r.text
                else:
                    import urllib.request
                    r = urllib.request.urlopen(url, timeout=15)
                    text = r.read().decode()
                raw = [l.strip() for l in text.splitlines() if l.strip()]
                # Normalize: strip socks5:// prefixes, skip non-socks5 entries
                normalized = []
                for line in raw:
                    addr = self._normalize_proxy(line)
                    if addr:
                        normalized.append(addr)
                self._log(f"  Fetched {len(normalized)} from {src}")
                all_proxies.update(normalized)
            except Exception as e:
                self._log(f"  Failed to fetch from {src}: {e}")
        return list(all_proxies)

    @staticmethod
    def _socks5_preflight(
        proxy_addr: str,
        connect_timeout: float = SOCKS5_CONNECT_TIMEOUT,
        handshake_timeout: float = SOCKS5_HANDSHAKE_TIMEOUT,
    ) -> bool:
        """Raw-socket SOCKS5 greeting check with kernel-level timeouts.

        This runs BEFORE handing the proxy to httpx. It's the only layer that
        reliably enforces a timeout on recv(): httpx's SOCKS5 transport can
        leave recv() blocked in the kernel indefinitely when a proxy accepts
        TCP but never completes the handshake.

        Sends the SOCKS5 greeting (VER=5, NMETHODS=1, METHODS=[no-auth]) and
        expects a 2-byte reply starting with 0x05. Returns True only if the
        proxy speaks SOCKS5 within the timeout budget.
        """
        try:
            host, _, port_raw = proxy_addr.partition(":")
            port = int(port_raw)
        except (ValueError, TypeError):
            return False
        if not host or port <= 0:
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

    def _test_proxy(self, proxy_addr: str):
        """Test a single proxy against VkusVill HTTPS (with SSL verification).
        Returns (addr, speed) or None. Rejects MITM proxies.

        Performs a raw-socket SOCKS5 preflight first so the expensive httpx
        probe never runs against a proxy that would hang its recv().
        """
        start = time.time()
        if not self._socks5_preflight(proxy_addr):
            self._track_event("test_fail", {"addr": proxy_addr, "reason": "socks5_preflight"})
            return None
        if self._probe_vkusvill(proxy_addr, verify_ssl=True):
            speed = time.time() - start
            self._track_event("found", {"addr": proxy_addr, "speed": round(speed, 2)})
            return (proxy_addr, speed)
        else:
            self._track_event("test_fail", {"addr": proxy_addr})
            return None

    def _load_cache(self) -> dict:
        """Load cached proxies from disk."""
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"updated_at": None, "proxies": []}

    def _save_cache(self):
        """Save cached proxies to disk."""
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(self._cache, f, indent=2)

    @staticmethod
    def get_event_stats() -> dict:
        """Aggregate proxy events from JSONL log into day/week/month stats."""
        from collections import defaultdict

        now = datetime.now()
        periods = {
            "today": 1,
            "week": 7,
            "month": 30,
        }

        # Initialize counters
        stats = {}
        for period in periods:
            stats[period] = {
                "found": 0,
                "removed": 0,
                "test_fail": 0,
                "refresh": 0,
                "refresh_tested": 0,
            }

        recent_events = []  # last 20 events for display

        try:
            with open(EVENTS_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    ts_str = entry.get("ts", "")
                    try:
                        ts = datetime.fromisoformat(ts_str)
                    except (ValueError, TypeError):
                        continue

                    age_days = (now - ts).total_seconds() / 86400
                    event = entry.get("event", "")

                    for period, max_days in periods.items():
                        if age_days <= max_days:
                            if event == "found":
                                stats[period]["found"] += 1
                            elif event == "removed":
                                stats[period]["removed"] += 1
                            elif event == "test_fail":
                                stats[period]["test_fail"] += 1
                            elif event == "refresh":
                                stats[period]["refresh"] += 1
                                stats[period]["refresh_tested"] += entry.get("tested", 0)

                    # Keep last 20 events
                    recent_events.append({
                        "ts": ts_str,
                        "event": event,
                        "addr": entry.get("addr", ""),
                        "speed": entry.get("speed"),
                        "pool_after": entry.get("pool_after"),
                        "pool_size": entry.get("pool_size"),
                    })

        except FileNotFoundError:
            pass
        except Exception:
            pass

        # For each period, compute success rate
        for period in periods:
            total_tests = stats[period]["found"] + stats[period]["test_fail"]
            if total_tests > 0:
                stats[period]["success_rate"] = round(
                    stats[period]["found"] / total_tests * 100, 1
                )
            else:
                stats[period]["success_rate"] = None

        return {
            "periods": stats,
            "recent": recent_events[-20:],
        }


# ── CLI test ──────────────────────────────────────────────────
if __name__ == "__main__":
    pm = ProxyManager()

    print("=== Test 1: Direct VkusVill probe ===")
    ok = pm.check_direct()
    print(f"  Direct: {'OK' if ok else 'BLOCKED'}")

    if not ok:
        print("\n=== Test 2: Find working proxy ===")
        proxy = pm.get_working_proxy()
        if proxy:
            print(f"  Working proxy: {proxy}")
            print(f"  Chrome flag: {pm.get_proxy_for_chrome()}")
        else:
            print("  No working proxy found")
    else:
        print("\n=== Direct works, testing proxy refresh anyway ===")
        count = pm.refresh_proxy_list()
        print(f"  Found {count} working proxies")

    print("\n=== Cache contents ===")
    for entry in pm._cache.get("proxies", [])[:5]:
        print(f"  {entry['addr']} ({entry['speed']:.1f}s)")

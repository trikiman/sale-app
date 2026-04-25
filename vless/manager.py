"""API-compatible replacement for :class:`proxy_manager.ProxyManager`.

:class:`VlessProxyManager` owns a long-lived :class:`vless.xray.XrayProcess`
and a pool of VLESS+Reality nodes. Callers interact with the same public
method surface as the legacy SOCKS5 ``ProxyManager`` — :meth:`get_working_proxy`
always returns ``"127.0.0.1:<xray-port>"`` when the pool is non-empty, and
node-level rotation happens inside xray via the ``random`` balancer.

The design is intentionally conservative: the refresh pipeline tests every
candidate node end-to-end before admission, and the VkusVill 4-hour cooldown
from the legacy manager carries over so misbehaving nodes are quarantined
without being permanently evicted.
"""
from __future__ import annotations

import atexit
import concurrent.futures
import json
import os
import socket
import threading
import time
from datetime import datetime
from pathlib import Path

try:
    import httpx  # noqa: F401 — presence guard only; we re-check per call
    HAS_HTTPX = True
except ImportError:  # pragma: no cover — CI installs httpx
    HAS_HTTPX = False

from vless import installer, pool_state, sources
from vless.config_gen import XRAY_LISTEN_HOST, XRAY_LISTEN_PORT, build_xray_config
from vless.parser import VlessNode
from vless.xray import XrayProcess, XrayStartupError, _atomic_write_text

_BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = _BASE_DIR / "data"
CACHE_DIR = _BASE_DIR / ".cache"
EVENTS_FILE = DATA_DIR / "proxy_events.jsonl"
COOLDOWNS_FILE = CACHE_DIR / "vkusvill_cooldowns.json"
XRAY_CONFIG_PATH = _BASE_DIR / "bin" / "xray" / "configs" / "active.json"
XRAY_LOG_PATH = _BASE_DIR / "bin" / "xray" / "logs" / "xray.log"

# API-compatible knobs lifted from proxy_manager.py. Changing any of these
# changes observable behaviour; keep them in sync.
MAX_CACHED = 30
MIN_HEALTHY = 7
CACHE_TTL = 86400  # 24h
DIRECT_CHECK_TTL = 60
VKUSVILL_COOLDOWN_S = 4 * 3600
PROBE_TIMEOUT = 8
VKUSVILL_URL = "https://vkusvill.ru/"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
)

# Refresh pipeline knobs
_REFRESH_MAX_TIME_S = 180
_NODE_TEST_CONCURRENCY = 8
_NODE_TEST_TIMEOUT_S = 12.0
_MAX_PER_SUBNET = 3


class VlessProxyManager:
    """Drop-in replacement for :class:`proxy_manager.ProxyManager`.

    Every public method mirrors the legacy SOCKS5 manager so existing callers
    (scraper, cart, backend, admin endpoints) keep working unchanged. The
    key semantic shift: ``get_working_proxy`` always returns the local xray
    SOCKS5 endpoint; true node rotation happens inside xray's ``random``
    balancer rather than in Python.
    """

    # ── Construction / lifecycle ────────────────────────────────

    def __init__(
        self,
        log_func=None,
        *,
        pool_path: Path | None = None,
        cooldowns_path: Path | None = None,
        events_path: Path | None = None,
        xray_config_path: Path | None = None,
        xray_log_path: Path | None = None,
        xray_binary: Path | None = None,
        auto_install_xray: bool = False,
        register_atexit: bool = True,
    ) -> None:
        self._log = log_func or (lambda msg: print(f"  [VLESS] {msg}"))
        self._lock = threading.RLock()
        self._pool_path = pool_path or (DATA_DIR / "vless_pool.json")
        self._cooldowns_path = cooldowns_path or COOLDOWNS_FILE
        self._events_path = events_path or EVENTS_FILE
        self._xray_config_path = xray_config_path or XRAY_CONFIG_PATH
        self._xray_log_path = xray_log_path or XRAY_LOG_PATH
        self._xray_binary = xray_binary
        self._auto_install_xray = auto_install_xray

        self._pool = pool_state.load(self._pool_path)
        self._cooldowns = self._load_cooldowns()
        self._direct_check = {"checked_at": 0.0, "ok": None}
        self._xray: XrayProcess | None = None
        self._last_config_reload: str | None = None
        self._last_crash_at: str | None = None

        self._prune_expired_cooldowns()

        if register_atexit:
            atexit.register(self._shutdown)

    # ── Legacy-API compatibility surface ───────────────────────

    def check_direct(self) -> bool:
        """Probe vkusvill.ru without a proxy. Returns True if reachable."""
        return self._probe_vkusvill(proxy=None)

    def check_direct_cached(self, ttl: int = DIRECT_CHECK_TTL) -> bool:
        """TTL cache over :meth:`check_direct`."""
        cached_ok = self._direct_check.get("ok")
        checked_at = self._direct_check.get("checked_at", 0.0)
        if cached_ok is not None and (time.time() - checked_at) < ttl:
            return bool(cached_ok)
        ok = self.check_direct()
        self.note_direct_result(ok)
        return ok

    def note_direct_result(self, ok: bool) -> None:
        self._direct_check = {"checked_at": time.time(), "ok": bool(ok)}

    def get_working_proxy(self, allow_refresh: bool = True) -> str | None:
        """Return ``"127.0.0.1:<xray-port>"`` when the pool is healthy.

        When the pool is empty and ``allow_refresh`` is True we call
        :meth:`ensure_pool` exactly like the legacy SOCKS5 manager did.
        The local xray subprocess is started lazily on the first hit.
        """
        if allow_refresh:
            self.ensure_pool()
        with self._lock:
            if not self._pool.get("nodes"):
                self._log("No VLESS nodes in pool — cannot produce a proxy")
                return None
            try:
                self._ensure_xray_running()
            except XrayStartupError as exc:
                self._log(f"xray startup failed: {exc}")
                return None
            inbound_port = self._xray.inbound_port if self._xray else XRAY_LISTEN_PORT
            addr = f"{XRAY_LISTEN_HOST}:{inbound_port}"
            self._log(f"Using xray bridge {addr} ({self.pool_count()} nodes in pool)")
            return addr

    def get_proxy_for_chrome(self) -> str | None:
        proxy = self.get_working_proxy()
        return f"socks5://{proxy}" if proxy else None

    def pool_count(self) -> int:
        return len(self._pool.get("nodes", []))

    def pool_healthy(self) -> bool:
        return self.pool_count() >= MIN_HEALTHY

    def remove_proxy(self, addr: str) -> None:
        """Remove a node from the pool or rotate away from the current bridge.

        Two forms:

        * ``addr == "127.0.0.1:10808"`` — the local xray bridge. The caller
          failed against "some upstream" but doesn't know which. We rotate
          by calling :meth:`mark_current_node_blocked`, which puts the
          presumed head-of-list node into the 4h VkusVill cooldown. With
          xray's ``leastPing`` balancer (phase 57-01) the head-of-list is
          as good a suspect as any.
        * ``addr`` is a VLESS host or host:port — direct node removal as
          before. Used by tests and tools that know the upstream identity.
        """
        rotate_local = False
        with self._lock:
            if addr.startswith(f"{XRAY_LISTEN_HOST}:"):
                self._log(
                    "remove_proxy called with local xray endpoint — "
                    "rotating via mark_current_node_blocked"
                )
                rotate_local = True
            else:
                host = addr.split(":", 1)[0]
                self._remove_host_and_restart(host, reason="remove_proxy")
        if rotate_local:
            # Released the lock above; mark_current_node_blocked re-acquires
            # it. RLock would also work but explicit release keeps the lock
            # graph obvious.
            self.mark_current_node_blocked("remove_proxy_local_addr")

    def next_proxy(self) -> str | None:
        """Rotate away from the currently-active VLESS node.

        xray chooses outbounds at random, so "next" here means "drop whichever
        node xray is presumed to be using and let the balancer pick again".
        Returns the xray endpoint if the pool is still non-empty.
        """
        with self._lock:
            nodes = self._pool.get("nodes", [])
            if nodes:
                # Pop the top node to ensure visible rotation — callers expect
                # that two consecutive next_proxy() calls probe different hosts.
                dropped = nodes[0].get("host", "")
                if dropped:
                    self._remove_host_and_restart(dropped, reason="next_proxy")
        return self.get_working_proxy()

    def mark_vkusvill_blocked(self, addr: str, reason: str = "timeout") -> None:
        """Put ``addr`` in the 4h VkusVill cooldown.

        ``addr`` is expected to be a VLESS host IP; callers that only know the
        local xray endpoint should use :meth:`mark_current_node_blocked`.
        """
        if addr.startswith(f"{XRAY_LISTEN_HOST}:"):
            self._log(
                "mark_vkusvill_blocked called with local xray endpoint — "
                "expected VLESS host IP. Use mark_current_node_blocked."
            )
            return
        host = addr.split(":", 1)[0]
        now = time.time()
        with self._lock:
            self._cooldowns[host] = {"blocked_at": now, "reason": reason}
            self._save_cooldowns()
            removed = self._remove_host_and_restart(host, reason=f"cooldown:{reason}")
        until = datetime.fromtimestamp(now + VKUSVILL_COOLDOWN_S).strftime("%H:%M")
        self._log(
            f"VkusVill cooldown ({reason}) for {host} until ~{until} "
            f"(removed={removed}, pool={self.pool_count()})"
        )
        self._track_event(
            "vkusvill_cooldown",
            {"addr": host, "reason": reason, "until_ts": now + VKUSVILL_COOLDOWN_S},
        )
        if self.pool_count() < MIN_HEALTHY:
            self._log(f"Pool below {MIN_HEALTHY} — will refresh on next use")

    def is_in_vkusvill_cooldown(self, addr: str) -> bool:
        entry = self._cooldowns.get(addr.split(":", 1)[0])
        if not entry:
            return False
        blocked_at = float(entry.get("blocked_at", 0.0))
        return (time.time() - blocked_at) < VKUSVILL_COOLDOWN_S

    def cooldown_addrs(self) -> set[str]:
        now = time.time()
        return {
            host
            for host, entry in self._cooldowns.items()
            if (now - float(entry.get("blocked_at", 0.0))) < VKUSVILL_COOLDOWN_S
        }

    @property
    def _cache(self) -> dict:
        """Read-only view compatible with the legacy SOCKS5 ``ProxyManager._cache``.

        Legacy callers (``backend/main.py::product_details``, admin refresh
        endpoint) treat ``_cache["proxies"]`` as a list of ``{"addr": ...}``
        dicts and then build ``socks5://<addr>`` URLs from them. The VLESS
        architecture collapses the whole pool behind a single local xray
        SOCKS5 inbound, so we expose exactly one synthetic entry pointing at
        the bridge when the pool is non-empty. The returned dict is a fresh
        copy — mutating it has no effect on real state, matching the
        semantics the shim contract promises.
        """
        nodes = self._pool.get("nodes", [])
        proxies: list[dict] = []
        if nodes:
            proxies.append(
                {
                    "addr": f"{XRAY_LISTEN_HOST}:{XRAY_LISTEN_PORT}",
                    "speed": 0.0,
                    "added_at": self._pool.get("updated_at"),
                }
            )
        return {
            "updated_at": self._pool.get("updated_at"),
            "proxies": proxies,
            "vkusvill_cooldowns": {
                host: dict(entry) for host, entry in self._cooldowns.items()
            },
        }

    def ensure_pool(self) -> int:
        """Refresh if the pool is below :data:`MIN_HEALTHY` or stale (>24h)."""
        count = self.pool_count()
        stale = self.is_cache_stale()
        if count >= MIN_HEALTHY and not stale:
            return count
        if stale:
            self._log(f"Daily refresh (cache > {CACHE_TTL // 3600}h old)")
        else:
            self._log(f"Pool low ({count}/{MIN_HEALTHY}) — refreshing...")
        existing = {
            entry.get("host")
            for entry in self._pool.get("nodes", [])
            if entry.get("host")
        }
        self.refresh_proxy_list(exclude=existing)
        total = self.pool_count()
        self._log(f"Pool now has {total} nodes")
        return total

    def refresh_proxy_list(self, exclude: set[str] | None = None) -> int:
        """Fetch → parse → geo-filter → probe → admit → rebuild xray.

        Returns the count of *newly-admitted* nodes. Callers compatible with
        the legacy SOCKS5 manager use the return value as a health signal
        ("how many new proxies did we find this cycle?"). Existing nodes that
        remain in the pool don't inflate the count.
        """
        self._log("Fetching VLESS list from igareck union...")
        try:
            text = sources.fetch_igareck_list()
        except Exception as exc:  # noqa: BLE001 — surface to operator
            self._log(f"Failed to fetch VLESS list: {exc}")
            return 0

        parsed, parse_errors = sources.parse_vless_list(text)
        self._log(f"Parsed {len(parsed)} nodes ({len(parse_errors)} parse errors)")
        if not parsed:
            return 0

        try:
            ru_nodes, rejected = sources.filter_ru_nodes(parsed)
        except Exception as exc:  # noqa: BLE001
            self._log(f"Geo-filter failed: {exc}")
            return 0
        self._log(f"Geo-filter: {len(ru_nodes)} RU / {len(rejected)} rejected")

        # Drop cooldown / excluded hosts before probing.
        self._prune_expired_cooldowns()
        cooling = self.cooldown_addrs()
        exclude = exclude or set()
        candidates: list[VlessNode] = []
        for node in ru_nodes:
            if node.host in cooling:
                continue
            if node.host in exclude and any(
                entry.get("host") == node.host for entry in self._pool.get("nodes", [])
            ):
                # Already in the pool — keep it but don't count as new admission.
                continue
            candidates.append(node)

        # Track the refresh start event so ops tooling sees we attempted.
        self._track_event(
            "vless_refresh_start",
            {
                "fetched": len(parsed),
                "parsed": len(parsed),
                "ru_filtered": len(ru_nodes),
                "candidates": len(candidates),
                "cooldown_skipped": len([n for n in ru_nodes if n.host in cooling]),
            },
        )

        if not candidates:
            self._log("No candidate nodes after filtering — keeping existing pool")
            return 0

        admitted = self._probe_candidates_in_parallel(candidates)
        if not admitted:
            self._log("Refresh produced no admitted nodes; pool unchanged")
            return 0

        admitted = self._apply_subnet_diversity(admitted)

        new_pool = pool_state.replace_nodes(self._pool, admitted, verified_country="RU")
        with self._lock:
            self._pool = new_pool
            pool_state.save(self._pool, self._pool_path)
            self._rebuild_and_restart_xray()
        for node in admitted:
            self._track_event(
                "vless_node_admitted",
                {"host": node.host, "port": node.port, "name": node.name[:120]},
            )
        return len(admitted)

    def is_cache_stale(self) -> bool:
        updated = self._pool.get("updated_at")
        if not updated:
            return True
        try:
            updated_dt = datetime.fromisoformat(updated)
        except (TypeError, ValueError):
            return True
        age = (datetime.now() - updated_dt).total_seconds()
        return age > CACHE_TTL

    # ── VLESS-specific helpers (additions) ─────────────────────

    def remove_vless_node(self, host: str) -> None:
        """Remove the node at ``host`` from the pool and restart xray."""
        with self._lock:
            self._remove_host_and_restart(host, reason="remove_vless_node")

    def mark_current_node_blocked(self, reason: str = "timeout") -> None:
        """Mark the first (presumed-active) node as VkusVill-blocked.

        xray's ``random`` balancer does not expose the currently-selected
        outbound via its admin API (we deliberately avoid that API to keep
        xray self-contained), so we treat the pool's head-of-list as the
        "likely culprit". Over a few probe failures the caller will churn
        through the top-of-pool and recover.
        """
        with self._lock:
            nodes = self._pool.get("nodes", [])
            if not nodes:
                self._log("mark_current_node_blocked called on empty pool — ignored")
                return
            host = nodes[0].get("host")
        if host:
            self.mark_vkusvill_blocked(host, reason=reason)

    def current_node(self) -> dict | None:
        """Return pool metadata for the most-likely active node (head of list)."""
        nodes = self._pool.get("nodes", [])
        return dict(nodes[0]) if nodes else None

    def xray_status(self) -> dict:
        """Diagnostic snapshot of the xray subprocess."""
        proc = self._xray
        pid: int | None = None
        running = False
        inbound_port = XRAY_LISTEN_PORT
        if proc is not None:
            inbound_port = proc.inbound_port
            if proc.is_running():
                running = True
                if proc._proc is not None:  # noqa: SLF001 — diagnostic only
                    pid = proc._proc.pid
        return {
            "running": running,
            "pid": pid,
            "inbound_port": inbound_port,
            "pool_size": self.pool_count(),
            "last_config_reload": self._last_config_reload,
            "last_crash_at": self._last_crash_at,
        }

    # ── Events + stats ─────────────────────────────────────────

    @staticmethod
    def get_event_stats() -> dict:
        """Aggregate proxy events into day/week/month stats.

        Preserves the exact shape returned by
        :meth:`proxy_manager.ProxyManager.get_event_stats` so admin endpoints
        continue to work unchanged.
        """
        now = datetime.now()
        periods = {"today": 1, "week": 7, "month": 30}
        stats: dict[str, dict] = {
            period: {
                "found": 0,
                "removed": 0,
                "test_fail": 0,
                "refresh": 0,
                "refresh_tested": 0,
            }
            for period in periods
        }
        recent_events: list[dict] = []
        try:
            with EVENTS_FILE.open("r", encoding="utf-8") as f:
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
                    except (TypeError, ValueError):
                        continue
                    age_days = (now - ts).total_seconds() / 86400
                    event = entry.get("event", "")
                    for period, max_days in periods.items():
                        if age_days > max_days:
                            continue
                        if event in ("found", "vless_node_admitted"):
                            stats[period]["found"] += 1
                        elif event in ("removed", "vless_node_removed"):
                            stats[period]["removed"] += 1
                        elif event == "test_fail":
                            stats[period]["test_fail"] += 1
                        elif event in ("refresh", "vless_refresh_start"):
                            stats[period]["refresh"] += 1
                            stats[period]["refresh_tested"] += int(
                                entry.get("candidates", entry.get("tested", 0) or 0)
                            )
                    recent_events.append(
                        {
                            "ts": ts_str,
                            "event": event,
                            "addr": entry.get("addr", entry.get("host", "")),
                            "speed": entry.get("speed"),
                            "pool_after": entry.get("pool_after"),
                            "pool_size": entry.get("pool_size"),
                        }
                    )
        except FileNotFoundError:
            pass
        except OSError:
            pass
        for period in periods:
            total = stats[period]["found"] + stats[period]["test_fail"]
            stats[period]["success_rate"] = (
                round(stats[period]["found"] / total * 100, 1) if total else None
            )
        return {"periods": stats, "recent": recent_events[-20:]}

    # ── Internals ──────────────────────────────────────────────

    def _log_write_error(self, exc: Exception, *, context: str) -> None:
        # Matching legacy behaviour: event/logging write errors never crash
        # the caller but always surface in the operator log.
        self._log(f"{context} failed: {exc}")

    def _track_event(self, event_type: str, data: dict | None = None) -> None:
        entry = {"ts": datetime.now().isoformat(), "event": event_type}
        if data:
            entry.update(data)
        try:
            self._events_path.parent.mkdir(parents=True, exist_ok=True)
            with self._events_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as exc:
            self._log_write_error(exc, context="events log")

    def _load_cooldowns(self) -> dict:
        if not self._cooldowns_path.exists():
            return {}
        try:
            with self._cooldowns_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save_cooldowns(self) -> None:
        try:
            self._cooldowns_path.parent.mkdir(parents=True, exist_ok=True)
            with self._cooldowns_path.open("w", encoding="utf-8") as f:
                json.dump(self._cooldowns, f, indent=2, ensure_ascii=False)
        except OSError as exc:
            self._log_write_error(exc, context="cooldowns save")

    def _prune_expired_cooldowns(self) -> int:
        if not self._cooldowns:
            return 0
        now = time.time()
        stale = [
            host
            for host, entry in self._cooldowns.items()
            if (now - float(entry.get("blocked_at", 0.0))) >= VKUSVILL_COOLDOWN_S
        ]
        if stale:
            for host in stale:
                self._cooldowns.pop(host, None)
            self._save_cooldowns()
            self._log(
                f"VkusVill cooldown expired for {len(stale)} host(s) "
                "(eligible for retest)"
            )
        return len(stale)

    def _probe_vkusvill(self, proxy: str | None = None, verify_ssl: bool = False) -> bool:
        """HTTP probe of vkusvill.ru; returns True only when the real catalog
        homepage is served — i.e. the IP is NOT VPN-flagged by VkusVill.

        VkusVill serves the real homepage for RU-egress IPs (final URL is
        ``https://vkusvill.ru/``, body never mentions ``vpn-detected``) and
        redirects VPN-flagged egresses to ``/vpn-detected/`` (either via a
        Location header we follow, or via a client-side bounce whose HTML
        still contains the literal ``vpn-detected`` substring).

        The admission check therefore requires:

        1. ``status_code == 200``
        2. The final URL (after ``follow_redirects=True``) does not contain
           ``/vpn-detected/``.
        3. The body does not contain the literal ``vpn-detected`` substring
           (catches client-side bounces whose initial status is still 200).
        4. The body contains ``vkusvill`` (defensive — rules out captive
           portals / DNS hijacks / connection-reset HTML from broken nodes).
        5. The body is at least ~20 KB — the real homepage is ~380 KB; the
           VPN-warning page we observed was ~35 KB but contained the marker;
           this floor just rules out tiny error pages without being brittle
           to VkusVill changing the VPN-page wording.

        The previous (PR #6) marker-list check has been removed: the markers
        we picked (``favoritesbtn`` / ``shopsmenu`` / ``personalcabinetmenu``)
        don't appear on the current homepage at all, so the check rejected
        100 % of otherwise-good RU-exit nodes.
        """
        if not HAS_HTTPX:
            return False
        import httpx

        kwargs: dict = {
            "timeout": PROBE_TIMEOUT,
            "verify": verify_ssl,
            "headers": {"User-Agent": UA},
            "follow_redirects": True,
        }
        if proxy:
            kwargs["proxy"] = f"socks5h://{proxy}"
        try:
            with httpx.Client(**kwargs) as client:
                resp = client.get(VKUSVILL_URL)
            if resp.status_code != 200:
                return False
            if "/vpn-detected/" in str(resp.url):
                return False
            if len(resp.text) < 20_000:
                return False
            body = resp.text.lower()
            if "vpn-detected" in body:
                return False
            return "vkusvill" in body
        except Exception:  # noqa: BLE001 — probe is best-effort
            return False

    def _probe_candidates_in_parallel(self, candidates: list[VlessNode]) -> list[VlessNode]:
        """Stand up a single-node xray per candidate on unique ports, probe, keep survivors.

        The probe is two-stage:

        1. ``_probe_vkusvill`` confirms the candidate can reach the real
           VkusVill catalog (rejects /vpn-detected/ and DNS failures).
        2. ``XrayProcess.verify_egress`` confirms the egress IP geolocates
           to RU. Restores plan-56 decision D-05 which v1.16 PR #7 dropped
           in favor of trusting the 🇷🇺 emoji label — see
           ``.planning/phases/56-vless-proxy-migration/INSPECTION-2026-04-23.md``
           section S5.

        Both stages run through the same per-candidate xray subprocess and
        share its lifetime — the subprocess is started once and stopped once
        per candidate.
        """
        if not candidates:
            return []
        binary = self._resolve_xray_binary()
        admitted: list[VlessNode] = []
        deadline = time.monotonic() + _REFRESH_MAX_TIME_S
        lock = threading.Lock()

        def _probe_one(node: VlessNode, idx: int) -> VlessNode | None:
            if time.monotonic() > deadline:
                return None
            test_port = 20000 + (idx % 10_000)
            test_config = _BASE_DIR / "bin" / "xray" / "configs" / f"probe-{idx}.json"
            test_log = _BASE_DIR / "bin" / "xray" / "logs" / f"probe-{idx}.log"
            config_dict = build_xray_config([node], listen_port=test_port)
            try:
                test_config.parent.mkdir(parents=True, exist_ok=True)
                test_config.write_text(
                    json.dumps(config_dict, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            except OSError:
                return None

            proc = XrayProcess(
                binary=binary,
                config_path=test_config,
                log_path=test_log,
                health_check_timeout=4.0,
                restart_limit=0,
            )
            try:
                proc.start()
            except XrayStartupError:
                return None
            start = time.monotonic()
            try:
                vkusvill_ok = self._probe_vkusvill(
                    proxy=f"{XRAY_LISTEN_HOST}:{test_port}",
                    verify_ssl=False,
                )
                if not vkusvill_ok:
                    return None
                # Restore plan-56 D-05: verify the egress IP actually
                # geolocates to RU. Phase-56 PR #7 dropped this check and
                # admitted FI/DE/NL/FR/PL exits labeled with 🇷🇺 emojis.
                # Phase 58-01: drop the explicit ``url=`` kwarg so the
                # call uses the multi-provider fallback chain. ipinfo.io
                # alone rate-limits ~70% of refresh probes; with the
                # chain (ipinfo.io → ipapi.co → ip-api.com) the same
                # refresh admits 2-3x more nodes.
                egress_ok, egress_country = proc.verify_egress(
                    expected_country="RU",
                    timeout=10.0,
                )
                if not egress_ok:
                    self._log(
                        f"Rejected {node.host} — egress_country={egress_country}"
                    )
                    node.extra["rejected_reason"] = f"egress_country={egress_country}"
                    return None
                node.extra["egress_country"] = egress_country
                node.extra["probe_speed_s"] = round(time.monotonic() - start, 2)
                return node
            finally:
                proc.stop(timeout=3.0)
                try:
                    test_config.unlink()
                except FileNotFoundError:
                    pass

        with concurrent.futures.ThreadPoolExecutor(max_workers=_NODE_TEST_CONCURRENCY) as pool:
            futures = {
                pool.submit(_probe_one, node, idx): node
                for idx, node in enumerate(candidates)
            }
            try:
                for fut in concurrent.futures.as_completed(
                    futures, timeout=_REFRESH_MAX_TIME_S
                ):
                    try:
                        result = fut.result(timeout=_NODE_TEST_TIMEOUT_S)
                    except (concurrent.futures.TimeoutError, Exception):  # noqa: BLE001
                        continue
                    if result is not None:
                        with lock:
                            admitted.append(result)
                    if len(admitted) >= MAX_CACHED:
                        break
            except concurrent.futures.TimeoutError:
                self._log("Candidate-probe outer timeout reached; continuing with partial pool")
            finally:
                # Best-effort cleanup; any stragglers are reaped by their own finally.
                for fut in futures:
                    fut.cancel()

        admitted.sort(key=lambda n: float(n.extra.get("probe_speed_s", 99.0)))
        return admitted

    @staticmethod
    def _apply_subnet_diversity(nodes: list[VlessNode]) -> list[VlessNode]:
        """Max :data:`_MAX_PER_SUBNET` nodes per /24, capped at :data:`MAX_CACHED`."""
        diverse: list[VlessNode] = []
        subnet_counts: dict[str, int] = {}
        for node in nodes:
            parts = node.host.split(".")
            subnet = ".".join(parts[:3]) if len(parts) == 4 else node.host
            cnt = subnet_counts.get(subnet, 0)
            if cnt >= _MAX_PER_SUBNET:
                continue
            diverse.append(node)
            subnet_counts[subnet] = cnt + 1
            if len(diverse) >= MAX_CACHED:
                break
        return diverse

    def _resolve_xray_binary(self) -> Path:
        if self._xray_binary is not None:
            return self._xray_binary
        if not installer.is_installed():
            if not self._auto_install_xray:
                raise XrayStartupError(
                    "xray binary not installed; run scripts/bootstrap_xray.py"
                )
            self._log("xray not installed — auto-installing pinned version")
            installer.install()
        return installer.binary_path()

    def _external_xray_listening(self) -> bool:
        """Return True if something (e.g. systemd xray) already listens on the bridge port.

        We only probe the default port — the in-process xray is tracked via
        :attr:`_xray` and takes precedence over this check.
        """
        try:
            with socket.create_connection(
                (XRAY_LISTEN_HOST, XRAY_LISTEN_PORT), timeout=1.0
            ):
                return True
        except OSError:
            return False

    def _ensure_xray_running(self) -> None:
        """Start xray on demand, rebuilding config from the current pool.

        If an external xray (e.g. ``saleapp-xray.service`` under systemd) is
        already bound to :data:`XRAY_LISTEN_PORT`, we skip the spawn and reuse
        that bridge — this lets multiple Python callers (backend, scheduler,
        ad-hoc scripts) share one supervised xray instead of racing to bind
        the same port.
        """
        if self._xray is not None and self._xray.is_running():
            return
        if self._external_xray_listening():
            self._log(
                f"External xray already listening on {XRAY_LISTEN_HOST}:"
                f"{XRAY_LISTEN_PORT} — reusing bridge"
            )
            return
        nodes = pool_state.nodes_from(self._pool)
        if not nodes:
            raise XrayStartupError("cannot start xray with empty pool")
        binary = self._resolve_xray_binary()
        config = build_xray_config(nodes)
        self._xray = XrayProcess(
            binary=binary,
            config_path=self._xray_config_path,
            log_path=self._xray_log_path,
            log_func=self._log,
        )
        self._xray.write_config(config)
        try:
            self._xray.start()
            self._last_config_reload = datetime.now().isoformat(timespec="seconds")
            self._track_event(
                "xray_start",
                {
                    "version": installer.XRAY_VERSION,
                    "pid": self._xray._proc.pid if self._xray._proc else None,  # noqa: SLF001
                    "inbound_port": self._xray.inbound_port,
                },
            )
        except XrayStartupError:
            self._last_crash_at = datetime.now().isoformat(timespec="seconds")
            raise

    def _write_active_config(self, config: dict) -> None:
        """Atomically write the xray config to :attr:`_xray_config_path`.

        The write is independent of the in-process ``XrayProcess`` so the
        file is available for an out-of-process (systemd) xray to consume.
        """
        _atomic_write_text(
            self._xray_config_path,
            json.dumps(config, indent=2, ensure_ascii=False),
        )

    def _rebuild_and_restart_xray(self) -> None:
        """Regenerate xray config from current pool and restart if already up.

        Always writes ``active.json`` to disk when the pool is non-empty, so
        an out-of-process (e.g. systemd-managed) xray can pick up the new
        config on its own restart cycle. The in-process xray, if any, is
        additionally restarted to pick up the change immediately.
        """
        nodes = pool_state.nodes_from(self._pool)
        if not nodes:
            # Empty pool — stop any running xray so callers see get_working_proxy=None.
            if self._xray is not None and self._xray.is_running():
                self._xray.stop()
                self._track_event("xray_stop", {"graceful": True, "reason": "empty pool"})
            return
        config = build_xray_config(nodes)
        # Persist config regardless of whether an in-process xray is tracked
        # — systemd-managed xray reads this file directly on restart.
        self._write_active_config(config)
        if self._xray is None:
            return  # in-process xray not tracked; systemd xray will pick up active.json
        try:
            self._xray.restart(new_config=config)
            self._last_config_reload = datetime.now().isoformat(timespec="seconds")
            self._track_event(
                "xray_start",
                {
                    "version": installer.XRAY_VERSION,
                    "pid": self._xray._proc.pid if self._xray._proc else None,  # noqa: SLF001
                    "inbound_port": self._xray.inbound_port,
                    "reason": "config_reload",
                },
            )
        except XrayStartupError as exc:
            self._last_crash_at = datetime.now().isoformat(timespec="seconds")
            self._log(f"xray restart failed: {exc}")

    def _remove_host_and_restart(self, host: str, *, reason: str) -> int:
        """Drop every entry for ``host``, rewrite pool, restart xray. Returns removed count."""
        before = self.pool_count()
        new_pool, removed = pool_state.remove_host(self._pool, host)
        if removed:
            self._pool = new_pool
            pool_state.save(self._pool, self._pool_path)
            self._log(f"Removed VLESS node {host} ({reason}); pool {before} → {self.pool_count()}")
            self._track_event(
                "vless_node_removed",
                {"host": host, "reason": reason, "pool_after": self.pool_count()},
            )
            self._rebuild_and_restart_xray()
        return removed

    def _shutdown(self) -> None:
        """atexit hook — make sure the xray subprocess isn't leaked."""
        proc = self._xray
        if proc is None or not proc.is_running():
            return
        pid = proc._proc.pid if proc._proc else None  # noqa: SLF001
        try:
            proc.stop(timeout=3.0)
        except Exception:  # noqa: BLE001 — best effort on interpreter shutdown
            return
        try:
            self._track_event("xray_stop", {"pid": pid, "graceful": True})
        except Exception:  # noqa: BLE001
            pass


# Silence "socket imported but unused" — kept as future hook for a port-in-use
# pre-check during probe fan-out without widening the module's import surface.
_ = socket
_ = os


__all__ = ["VlessProxyManager", "MIN_HEALTHY", "VKUSVILL_COOLDOWN_S"]

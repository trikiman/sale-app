"""Unit + optional live tests for :class:`vless.manager.VlessProxyManager`.

The unit suite stages every manager instance against ``tmp_path``: pool,
cooldowns, events log, and xray binary/config paths all redirect there, so
tests never touch the real ``data/`` or ``bin/`` trees. xray itself is
mocked via a fake :class:`vless.xray.XrayProcess` so the tests run fast and
without network.

The single ``@pytest.mark.integration`` test requires ``RUN_LIVE=1`` and
exercises the real fetch → parse → probe → admit → restart pipeline end-to
end against the live igareck source.
"""
from __future__ import annotations

import importlib
import inspect
import json
import os
import shutil
from pathlib import Path
from typing import Iterable

import pytest

from vless import manager as manager_mod
from vless.manager import MIN_HEALTHY, VlessProxyManager
from vless.parser import VlessNode


# ── Test helpers ──────────────────────────────────────────────


class FakeXrayProcess:
    """In-memory substitute for :class:`vless.xray.XrayProcess`.

    Stores the config it was handed, tracks start/stop/restart counts, and
    exposes a ``fail_next_start`` flag so tests can simulate startup
    failures without spawning a real subprocess.
    """

    instances: list["FakeXrayProcess"] = []
    # Default egress verification result. Tests that exercise the candidate
    # admission path can override this class-level attribute (or the
    # per-instance attribute) to simulate non-RU egress without touching the
    # real ipinfo.io probe.
    verify_egress_result: tuple[bool, str] = (True, "RU")

    def __init__(self, *args, **kwargs) -> None:
        self.config_path = Path(kwargs["config_path"])
        self.log_path = Path(kwargs.get("log_path") or self.config_path.with_suffix(".log"))
        self._binary = kwargs.get("binary")
        self._running = False
        self._started = 0
        self._stopped = 0
        self._restarted = 0
        self._writes = 0
        self._verify_egress_calls: list[dict] = []
        self.fail_next_start = False
        self._proc = _FakeProcHandle()
        type(self).instances.append(self)

    # lifecycle ---------------------------------------------------

    def start(self) -> None:
        self._started += 1
        if self.fail_next_start:
            self.fail_next_start = False
            from vless.xray import XrayStartupError

            raise XrayStartupError("fake startup failure")
        self._running = True

    def stop(self, *, timeout: float = 5.0) -> None:
        self._stopped += 1
        self._running = False

    def restart(self, *, new_config: dict | None = None) -> None:
        self._restarted += 1
        if new_config is not None:
            self.write_config(new_config)
        self.stop()
        self.start()

    def write_config(self, config: dict) -> None:
        self._writes += 1
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    # diagnostics -------------------------------------------------

    def verify_egress(
        self,
        *,
        expected_country: str = "RU",
        timeout: float = 10.0,
        url: str = "https://ipinfo.io/json",
    ) -> tuple[bool, str]:
        self._verify_egress_calls.append(
            {"expected_country": expected_country, "timeout": timeout, "url": url}
        )
        return type(self).verify_egress_result

    def is_running(self) -> bool:
        return self._running

    def health_check(self) -> bool:
        return self._running

    @property
    def inbound_port(self) -> int:
        if not self.config_path.exists():
            return 10808
        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return 10808
        for inbound in data.get("inbounds", []):
            if inbound.get("protocol") == "socks":
                port = inbound.get("port")
                if isinstance(port, int):
                    return port
        return 10808


class _FakeProcHandle:
    pid = 4242


@pytest.fixture
def stub_xray(monkeypatch: pytest.MonkeyPatch):
    """Swap the real XrayProcess for FakeXrayProcess in the manager module.

    Also blocks any accidental live network hits: tests that need the
    refresh pipeline monkeypatch the real functions explicitly; any other
    call raises and fails the test loudly so we don't regress to silent
    network dependencies.
    """
    FakeXrayProcess.instances.clear()
    FakeXrayProcess.verify_egress_result = (True, "RU")
    monkeypatch.setattr(manager_mod, "XrayProcess", FakeXrayProcess)
    monkeypatch.setattr(
        manager_mod.installer, "is_installed", lambda: True
    )
    monkeypatch.setattr(
        manager_mod.installer,
        "binary_path",
        lambda: Path("/fake/xray"),
    )

    def _network_tripwire(*_a, **_kw):
        raise AssertionError(
            "fetch_all_sources called from a unit test — monkeypatch it explicitly"
        )

    def _geo_tripwire(*_a, **_kw):
        raise AssertionError(
            "filter_ru_nodes called from a unit test — monkeypatch it explicitly"
        )

    monkeypatch.setattr(manager_mod.sources, "fetch_igareck_list", _network_tripwire)
    monkeypatch.setattr(manager_mod.sources, "fetch_all_sources", _network_tripwire)
    monkeypatch.setattr(manager_mod.sources, "filter_ru_nodes", _geo_tripwire)
    yield FakeXrayProcess
    FakeXrayProcess.instances.clear()


@pytest.fixture
def paths(tmp_path: Path) -> dict[str, Path]:
    """Isolated filesystem layout for one manager instance."""
    pool = tmp_path / "data" / "vless_pool.json"
    cooldowns = tmp_path / ".cache" / "vkusvill_cooldowns.json"
    events = tmp_path / "data" / "proxy_events.jsonl"
    xray_config = tmp_path / "bin" / "xray" / "configs" / "active.json"
    xray_log = tmp_path / "bin" / "xray" / "logs" / "xray.log"
    return {
        "pool": pool,
        "cooldowns": cooldowns,
        "events": events,
        "xray_config": xray_config,
        "xray_log": xray_log,
    }


def _make_pool(tmp_pool: Path, n: int, *, base_ip: str = "185.1.2") -> None:
    """Write a pool file with ``n`` fabricated RU entries."""
    shutil.rmtree(tmp_pool.parent, ignore_errors=True)
    tmp_pool.parent.mkdir(parents=True, exist_ok=True)
    nodes = []
    for i in range(n):
        nodes.append(
            {
                "uuid": f"{i:08x}-0000-0000-0000-000000000000",
                "host": f"{base_ip}.{10 + i}",
                "port": 443,
                "name": f"RU Node {i}",
                "reality_pbk": f"pbk-{i}",
                "reality_sni": "www.microsoft.com",
                "reality_sid": "",
                "reality_spx": "",
                "reality_fp": "chrome",
                "flow": "xtls-rprx-vision",
                "transport": "tcp",
                "encryption": "none",
                "header_type": "none",
                "extra": {},
                "verified_country": "RU",
                "verified_at": "2026-04-22T23:00:00",
                "last_success_at": None,
                "success_count": 0,
                "failure_count": 0,
            }
        )
    tmp_pool.write_text(
        json.dumps({"updated_at": "2026-04-22T23:15:00", "nodes": nodes}, indent=2),
        encoding="utf-8",
    )


def _manager(paths: dict[str, Path], **overrides) -> VlessProxyManager:
    return VlessProxyManager(
        log_func=lambda _m: None,
        pool_path=paths["pool"],
        cooldowns_path=paths["cooldowns"],
        events_path=paths["events"],
        xray_config_path=paths["xray_config"],
        xray_log_path=paths["xray_log"],
        xray_binary=Path("/fake/xray"),
        register_atexit=False,
        **overrides,
    )


# ── Tests ─────────────────────────────────────────────────────


def test_get_working_proxy_returns_local_xray_endpoint(stub_xray, paths) -> None:
    _make_pool(paths["pool"], n=5)
    pm = _manager(paths)
    assert pm.get_working_proxy(allow_refresh=False) == "127.0.0.1:10808"
    inst = stub_xray.instances[-1]
    assert inst.is_running()
    assert inst._started == 1


def test_get_working_proxy_returns_none_when_pool_empty(stub_xray, paths) -> None:
    pm = _manager(paths)
    assert pm.get_working_proxy(allow_refresh=False) is None
    assert not stub_xray.instances  # xray must NOT have started


def test_get_working_proxy_starts_xray_lazily(stub_xray, paths) -> None:
    _make_pool(paths["pool"], n=3)
    pm = _manager(paths)
    # Constructor must not have touched xray.
    assert not stub_xray.instances
    pm.get_working_proxy(allow_refresh=False)
    assert len(stub_xray.instances) == 1


def test_get_proxy_for_chrome_formats_socks5_prefix(stub_xray, paths) -> None:
    _make_pool(paths["pool"], n=1)
    pm = _manager(paths)
    assert pm.get_proxy_for_chrome() == "socks5://127.0.0.1:10808"


def test_pool_count_and_healthy_reflect_node_count(stub_xray, paths) -> None:
    _make_pool(paths["pool"], n=MIN_HEALTHY)
    pm = _manager(paths)
    assert pm.pool_count() == MIN_HEALTHY
    assert pm.pool_healthy() is True

    _make_pool(paths["pool"], n=MIN_HEALTHY - 1)
    pm2 = _manager(paths)
    assert pm2.pool_count() == MIN_HEALTHY - 1
    assert pm2.pool_healthy() is False


def test_remove_proxy_with_local_endpoint_rotates_via_mark_current_node_blocked(
    stub_xray, paths, monkeypatch
) -> None:
    """Phase 57-02: ``remove_proxy('127.0.0.1:10808')`` is no longer a no-op.

    The local xray bridge address is what every backend caller has access to
    (they only see SOCKS5, not the upstream VLESS host). When the caller hits
    a transient TLS error, ``remove_proxy(bridge)`` must now rotate by
    putting the presumed-active head-of-list node into the VkusVill cooldown
    via ``mark_current_node_blocked`` — otherwise the next request hits the
    same stuck node and the ``leastPing`` balancer gets no signal.
    """
    _make_pool(paths["pool"], n=3)
    pm = _manager(paths)
    calls: list[str] = []
    monkeypatch.setattr(
        pm,
        "mark_current_node_blocked",
        lambda reason="timeout": calls.append(reason),
    )
    pm.remove_proxy("127.0.0.1:10808")
    assert calls == ["remove_proxy_local_addr"]
    # Pool count is unchanged at the call boundary — cooldown is what gates
    # the head-of-list out, not direct removal.
    assert pm.pool_count() == 3


def test_cache_property_exposes_bridge_when_pool_non_empty(stub_xray, paths) -> None:
    """Backend endpoints (``product_details``, admin refresh) still read
    ``pm._cache["proxies"]`` from the legacy SOCKS5 contract. The bridge
    must appear as a single synthetic entry so ``socks5://{addr}`` points
    at the local xray inbound."""
    _make_pool(paths["pool"], n=3)
    pm = _manager(paths)
    cache = pm._cache
    assert isinstance(cache, dict)
    assert list(cache["proxies"]) == [
        {"addr": "127.0.0.1:10808", "speed": 0.0, "added_at": cache["updated_at"]}
    ]
    # Callers compose ``socks5://{addr}`` — must yield the xray endpoint.
    assert f"socks5://{cache['proxies'][0]['addr']}" == "socks5://127.0.0.1:10808"


def test_cache_property_empty_when_pool_empty(stub_xray, paths) -> None:
    pm = _manager(paths)
    assert pm._cache["proxies"] == []


def test_cache_property_is_read_only_snapshot(stub_xray, paths) -> None:
    """Mutating the returned dict must not leak into real manager state —
    it's a view, not a handle."""
    _make_pool(paths["pool"], n=2)
    pm = _manager(paths)
    snapshot = pm._cache
    snapshot["proxies"].clear()
    snapshot["vkusvill_cooldowns"]["9.9.9.9"] = {"blocked_at": 0, "reason": "oops"}
    fresh = pm._cache
    assert len(fresh["proxies"]) == 1  # still has the bridge entry
    assert "9.9.9.9" not in fresh["vkusvill_cooldowns"]


class _FakeHTTPXClient:
    """Minimal httpx.Client stand-in for :meth:`_probe_vkusvill` tests.

    The real probe does ``with httpx.Client(**kwargs) as client: client.get(...)``
    and inspects ``resp.status_code``, ``resp.url``, and ``resp.text``. We
    record the kwargs the probe passed so the pytest can assert on them, and
    serve a canned response shaped like an httpx response.
    """

    last_kwargs: dict = {}

    def __init__(self, **kwargs):
        type(self).last_kwargs = kwargs
        self._response = kwargs.pop("_response")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, url):  # noqa: ARG002 — URL fixed by the probe
        return self._response


class _FakeResponse:
    def __init__(self, status_code: int, url: str, text: str) -> None:
        self.status_code = status_code
        self.url = url
        self.text = text


def _install_fake_httpx(monkeypatch, *, status_code: int, url: str, body: str) -> None:
    """Patch ``httpx.Client`` inside the probe to return a canned response."""
    import httpx

    response = _FakeResponse(status_code=status_code, url=url, text=body)

    def _factory(**kwargs):
        return _FakeHTTPXClient(_response=response, **kwargs)

    monkeypatch.setattr(httpx, "Client", _factory)


# Real catalog homepage is ~380 KB — pad a brand-containing body past the
# 20 KB floor so the probe treats it as a real response.
_HOMEPAGE_SNIPPET = (
    "<html><head><title>ВкусВилл</title></head><body>"
    "<script>window.SITE=\"vkusvill\";</script>"
    "<a class=\"favoritesBtn\">favs</a>"
    "<nav id=\"shopsMenu\">shops</nav>"
    "</body></html>"
    + ("<!-- filler to exceed 20KB floor -->\n" * 800)
)
_VPN_PAGE_SNIPPET = (
    "<html><head><title>VkusVill — VPN</title></head><body>"
    "<h1>Доступ ограничен: используется VPN. "
    "Please visit /vpn-detected/</h1>"
    "</body></html>"
)


def test_probe_vkusvill_admits_real_homepage(stub_xray, paths, monkeypatch) -> None:
    """Real catalog homepage (200, >20 KB, brand, no /vpn-detected/) passes."""
    pm = _manager(paths)
    _install_fake_httpx(
        monkeypatch,
        status_code=200,
        url="https://vkusvill.ru/",
        body=_HOMEPAGE_SNIPPET,
    )
    assert pm._probe_vkusvill(proxy=None) is True


def test_probe_vkusvill_rejects_vpn_detected_landing(stub_xray, paths, monkeypatch) -> None:
    """200 that final-redirects to /vpn-detected/ must be rejected."""
    pm = _manager(paths)
    _install_fake_httpx(
        monkeypatch,
        status_code=200,
        url="https://vkusvill.ru/vpn-detected/?back_vpn_url=%2F",
        body=_HOMEPAGE_SNIPPET,  # size OK, but URL is the VPN landing
    )
    assert pm._probe_vkusvill(proxy=None) is False


def test_probe_vkusvill_rejects_body_with_vpn_detected_marker(
    stub_xray, paths, monkeypatch
) -> None:
    """A 200 whose body contains 'vpn-detected' (client-side bounce) rejects.

    Covers the case where the initial response arrives at ``/`` but contains
    a JS redirect / warning referencing ``vpn-detected``. Independent of the
    final URL check so we catch pages that redirect the user agent but
    haven't been followed by the HTTP client yet.
    """
    pm = _manager(paths)
    big_vpn_body = _VPN_PAGE_SNIPPET + ("x" * 30_000) + " vkusvill"
    _install_fake_httpx(
        monkeypatch,
        status_code=200,
        url="https://vkusvill.ru/",
        body=big_vpn_body,
    )
    assert pm._probe_vkusvill(proxy=None) is False


def test_probe_vkusvill_rejects_tiny_body(stub_xray, paths, monkeypatch) -> None:
    """A 200 with a < 20 KB body (captive portal / error shim) rejects."""
    pm = _manager(paths)
    _install_fake_httpx(
        monkeypatch,
        status_code=200,
        url="https://vkusvill.ru/",
        body="<html>vkusvill tiny</html>",
    )
    assert pm._probe_vkusvill(proxy=None) is False


def test_probe_vkusvill_rejects_non_200(stub_xray, paths, monkeypatch) -> None:
    pm = _manager(paths)
    _install_fake_httpx(
        monkeypatch,
        status_code=503,
        url="https://vkusvill.ru/",
        body=_HOMEPAGE_SNIPPET,
    )
    assert pm._probe_vkusvill(proxy=None) is False


def _ru_candidates(n: int) -> list[VlessNode]:
    """Build ``n`` synthetic candidates for ``_probe_candidates_in_parallel``."""
    out: list[VlessNode] = []
    for i in range(n):
        out.append(
            VlessNode(
                uuid=f"{i:08x}-0000-0000-0000-000000000000",
                host=f"10.0.0.{10 + i}",
                port=443,
                name=f"RU Probe {i}",
                reality_pbk=f"pbk-{i}",
                reality_sni="www.microsoft.com",
                reality_sid="",
                reality_spx="",
                reality_fp="chrome",
                flow="xtls-rprx-vision",
                transport="tcp",
                encryption="none",
                header_type="none",
                extra={},
                security="reality",
            )
        )
    return out


def test_probe_candidates_admits_ru_egress(stub_xray, paths, monkeypatch) -> None:
    """Phase 57-03: candidates with verified RU egress are admitted and
    annotated with ``extra["egress_country"] = "RU"`` for diagnostics."""
    pm = _manager(paths)
    monkeypatch.setattr(pm, "_tcp_prefilter_candidates", lambda c: list(c))
    monkeypatch.setattr(pm, "_probe_vkusvill", lambda **_kw: True)
    FakeXrayProcess.verify_egress_result = (True, "RU")
    admitted = pm._probe_candidates_in_parallel(_ru_candidates(2))
    assert len(admitted) == 2
    for node in admitted:
        assert node.extra.get("egress_country") == "RU"
        assert "rejected_reason" not in node.extra


def test_probe_candidates_rejects_non_ru_egress(stub_xray, paths, monkeypatch) -> None:
    """Phase 57-03: candidates whose egress is not RU must NOT be admitted,
    even if they pass the VkusVill probe.

    Regression guard for ``.planning/phases/56-vless-proxy-migration/
    INSPECTION-2026-04-23.md`` section S5: v1.16 PR #7 dropped this check
    and admitted FI/DE/NL/FR/PL exits labeled with 🇷🇺 emojis, breaking
    plan decision D-05.
    """
    pm = _manager(paths)
    monkeypatch.setattr(pm, "_tcp_prefilter_candidates", lambda c: list(c))
    monkeypatch.setattr(pm, "_probe_vkusvill", lambda **_kw: True)
    FakeXrayProcess.verify_egress_result = (False, "DE")
    admitted = pm._probe_candidates_in_parallel(_ru_candidates(3))
    assert admitted == [], "DE-egress candidates must not be admitted"


def test_probe_candidates_skips_egress_when_vkusvill_probe_fails(
    stub_xray, paths, monkeypatch
) -> None:
    """If the cheap VkusVill probe rejects the candidate, the more expensive
    egress probe must NOT run — saves ~1-2s per dead node during refresh."""
    pm = _manager(paths)
    monkeypatch.setattr(pm, "_tcp_prefilter_candidates", lambda c: list(c))
    monkeypatch.setattr(pm, "_probe_vkusvill", lambda **_kw: False)
    admitted = pm._probe_candidates_in_parallel(_ru_candidates(2))
    assert admitted == []
    for inst in stub_xray.instances:
        assert inst._verify_egress_calls == [], (
            "verify_egress was called despite vkusvill probe failing — "
            "phase 57-03 ordering is wrong"
        )


def test_probe_candidates_propagates_egress_error_message(
    stub_xray, paths, monkeypatch
) -> None:
    """``XrayProcess.verify_egress`` returns ``(False, "<error>")`` on
    network errors. The rejected_reason must capture the error so operators
    can diagnose pool-shrink (rate-limited ipinfo.io vs. real non-RU exit)."""
    pm = _manager(paths)
    monkeypatch.setattr(pm, "_tcp_prefilter_candidates", lambda c: list(c))
    monkeypatch.setattr(pm, "_probe_vkusvill", lambda **_kw: True)
    FakeXrayProcess.verify_egress_result = (False, "ConnectError: probe timed out")
    admitted = pm._probe_candidates_in_parallel(_ru_candidates(1))
    assert admitted == []


def test_tcp_prefilter_drops_unreachable_candidates(stub_xray, paths, monkeypatch) -> None:
    """v1.26 Phase 84.4: ``_tcp_prefilter_candidates`` rejects nodes
    whose ``host:port`` doesn't open in 2s. Live evidence on EC2
    (2026-05-14) showed 4 of 5 sampled candidates were dead Azure exits
    timing out at the TCP layer; pre-filtering them saves ~6s of xray
    probe time per dead node.

    Rejected nodes are stamped with ``extra["rejected_reason"] =
    "tcp_unreachable"`` so the existing classifier in
    ``refresh_proxy_list`` quarantines them at the soft tier (60s).
    """
    import socket as _socket

    class _FakeSock:
        def __enter__(self): return self
        def __exit__(self, *exc): return False

    def _fake_create_connection(addr, timeout=None):
        host, _port = addr
        # Only 10.0.0.10 (the first synthetic host) is reachable; every
        # other synthetic candidate gets a TCP-layer rejection.
        if host == "10.0.0.10":
            return _FakeSock()
        raise _socket.timeout("simulated TCP timeout")

    monkeypatch.setattr(manager_mod.socket, "create_connection", _fake_create_connection)

    pm = _manager(paths)
    candidates = _ru_candidates(4)  # hosts 10.0.0.10 through 10.0.0.13
    survivors = pm._tcp_prefilter_candidates(candidates)

    survivor_hosts = {n.host for n in survivors}
    assert survivor_hosts == {"10.0.0.10"}, (
        f"only the reachable host should survive — got {survivor_hosts}"
    )
    # Rejected nodes get the canonical reason stamp so refresh_proxy_list's
    # classifier can route them to the soft-tier (60s) quarantine.
    rejected = [n for n in candidates if n.host != "10.0.0.10"]
    assert {n.extra.get("rejected_reason") for n in rejected} == {"tcp_unreachable"}, (
        "TCP-dead nodes must be stamped with rejected_reason='tcp_unreachable'"
    )


def test_tcp_prefilter_runs_before_xray_in_full_probe_pipeline(
    stub_xray, paths, monkeypatch
) -> None:
    """v1.26 Phase 84.4: when every candidate is TCP-dead,
    ``_probe_candidates_in_parallel`` must short-circuit and never spin
    up an xray subprocess.

    Regression guard: budget math only works if dead-on-TCP nodes don't
    pay the ~6s xray setup + probe cost. If a future refactor reorders
    the stages, this test fails.
    """
    import socket as _socket

    def _all_tcp_dead(addr, timeout=None):  # noqa: ARG001
        raise _socket.timeout("simulated — every candidate is dead at TCP")

    monkeypatch.setattr(manager_mod.socket, "create_connection", _all_tcp_dead)

    pm = _manager(paths)
    # If TCP filter ran AFTER xray, _probe_vkusvill would be called; we
    # patch it as a tripwire so the test fails loudly if that happens.
    def _probe_tripwire(**_kw):  # pragma: no cover — must NOT be called
        raise AssertionError(
            "TCP pre-filter did not short-circuit — xray probe ran on "
            "TCP-dead candidate (Phase 84.4 ordering invariant violated)"
        )
    monkeypatch.setattr(pm, "_probe_vkusvill", _probe_tripwire)

    candidates = _ru_candidates(3)
    # Snapshot xray instance count before — Phase 84.4 invariant says it
    # MUST stay flat when TCP filter rejects everything.
    before = len(stub_xray.instances)
    admitted = pm._probe_candidates_in_parallel(candidates)
    after = len(stub_xray.instances)

    assert admitted == [], "all candidates were TCP-dead; admitted must be empty"
    assert after == before, (
        f"xray subprocess was started for TCP-dead candidate "
        f"(before={before}, after={after}) — Phase 84.4 short-circuit failed"
    )
    # All candidates carry the TCP-unreachable reason so the caller's
    # quarantine classifier puts them in the soft-tier bucket.
    assert all(n.extra.get("rejected_reason") == "tcp_unreachable" for n in candidates)


def test_probe_vkusvill_builds_socks5h_proxy_url(stub_xray, paths, monkeypatch) -> None:
    """When a proxy addr is passed, the probe must use ``socks5h://`` so DNS
    resolves inside the SOCKS proxy (so VLESS bridges get vkusvill.ru's
    real IP, not the local resolver's)."""
    pm = _manager(paths)
    _install_fake_httpx(
        monkeypatch,
        status_code=200,
        url="https://vkusvill.ru/",
        body=_HOMEPAGE_SNIPPET,
    )
    pm._probe_vkusvill(proxy="127.0.0.1:10808")
    assert _FakeHTTPXClient.last_kwargs.get("proxy") == "socks5h://127.0.0.1:10808"


def test_remove_proxy_with_vless_host_removes_and_restarts(stub_xray, paths) -> None:
    _make_pool(paths["pool"], n=3)
    pm = _manager(paths)
    pm.get_working_proxy(allow_refresh=False)  # lazy start
    inst = stub_xray.instances[-1]
    pm.remove_proxy("185.1.2.11:443")
    assert pm.pool_count() == 2
    assert inst._restarted >= 1


def test_remove_vless_node_rebuilds_config(stub_xray, paths) -> None:
    _make_pool(paths["pool"], n=3)
    pm = _manager(paths)
    pm.get_working_proxy(allow_refresh=False)
    pm.remove_vless_node("185.1.2.12")
    assert pm.pool_count() == 2
    final_cfg = json.loads(paths["xray_config"].read_text(encoding="utf-8"))
    vless_outbounds = [ob for ob in final_cfg["outbounds"] if ob.get("protocol") == "vless"]
    assert len(vless_outbounds) == 2


def test_vkusvill_cooldown_moves_host_out_of_pool(stub_xray, paths) -> None:
    _make_pool(paths["pool"], n=3)
    pm = _manager(paths)
    pm.mark_vkusvill_blocked("185.1.2.10", reason="timeout")
    assert pm.pool_count() == 2
    assert pm.is_in_vkusvill_cooldown("185.1.2.10")
    assert "185.1.2.10" in pm.cooldown_addrs()


def test_cooldown_pruning_on_startup(stub_xray, paths) -> None:
    import time as _time

    paths["cooldowns"].parent.mkdir(parents=True, exist_ok=True)
    paths["cooldowns"].write_text(
        json.dumps(
            {
                # Expired: 5h ago, beyond the 4h window.
                "1.1.1.1": {"blocked_at": _time.time() - 18000, "reason": "old"},
                "2.2.2.2": {"blocked_at": _time.time() - 18001, "reason": "old"},
                # Active: 1 minute ago.
                "3.3.3.3": {"blocked_at": _time.time() - 60, "reason": "recent"},
            }
        ),
        encoding="utf-8",
    )
    _make_pool(paths["pool"], n=1)
    pm = _manager(paths)
    cooling = pm.cooldown_addrs()
    assert cooling == {"3.3.3.3"}


def test_next_proxy_rotates_head_of_pool(stub_xray, paths) -> None:
    _make_pool(paths["pool"], n=3)
    pm = _manager(paths)
    first = pm.get_working_proxy(allow_refresh=False)
    assert first == "127.0.0.1:10808"
    # next_proxy drops the top host from the pool and rebuilds xray config.
    pm.next_proxy()
    assert pm.pool_count() == 2
    cfg = json.loads(paths["xray_config"].read_text(encoding="utf-8"))
    hosts = [
        ob["settings"]["vnext"][0]["address"]
        for ob in cfg["outbounds"]
        if ob.get("protocol") == "vless"
    ]
    assert "185.1.2.10" not in hosts, "rotated host must have been dropped"


def test_events_emitted_on_refresh(stub_xray, paths, monkeypatch) -> None:
    _make_pool(paths["pool"], n=0)
    pm = _manager(paths)

    sample = [
        VlessNode(
            uuid="00000000-0000-0000-0000-000000000001",
            host=f"185.1.2.{20 + i}",
            port=443,
            name=f"R {i}",
            reality_pbk=f"pbk-{i}",
            reality_sni="www.microsoft.com",
        )
        for i in range(3)
    ]
    monkeypatch.setattr(manager_mod.sources, "fetch_igareck_list", lambda: "_fake_")
    monkeypatch.setattr(manager_mod.sources, "fetch_all_sources", lambda **_kw: "_fake_aggregator_")
    monkeypatch.setattr(
        manager_mod.sources,
        "parse_vless_list",
        lambda _text: (sample, []),
    )
    monkeypatch.setattr(
        manager_mod.sources,
        "filter_ru_nodes",
        lambda nodes: (list(nodes), []),
    )

    # Every candidate "probes ok".
    def fake_probe(self, candidates):
        for n in candidates:
            n.extra["probe_speed_s"] = 0.5
        return list(candidates)

    monkeypatch.setattr(
        VlessProxyManager, "_probe_candidates_in_parallel", fake_probe
    )

    admitted = pm.refresh_proxy_list()
    assert admitted == 3
    assert pm.pool_count() == 3
    events = _load_events(paths["events"])
    event_types = [e["event"] for e in events]
    assert "vless_refresh_start" in event_types
    assert event_types.count("vless_node_admitted") == 3


def test_pre_probe_dedup_collapses_duplicate_host_port_entries(stub_xray, paths, monkeypatch) -> None:
    """v1.26 Phase 84.1: pre-probe dedup by (host, port).

    The igareck union ships the same `host:port` re-listed under
    different SNI/PBK/transport variants. Without pre-probe dedup the
    expensive `_probe_candidates_in_parallel` runs once per duplicate,
    wasting probe slots and producing the "same IP triple" admin UI bug.

    This test pins:
      1. The probe loop receives ONE entry per (host, port).
      2. The funnel log's vless_refresh_start event reports
         upstream_dups_dropped > 0.
    """
    _make_pool(paths["pool"], n=0)
    pm = _manager(paths)

    # 5 URIs but only 2 unique (host, port) pairs:
    #   185.1.2.20:443  x3  (different SNI / PBK variants)
    #   185.1.2.21:443  x2
    sample = [
        VlessNode(uuid="u1", host="185.1.2.20", port=443, name="A1",
                  reality_pbk="pbk-a", reality_sni="microsoft.com"),
        VlessNode(uuid="u1", host="185.1.2.20", port=443, name="A2",
                  reality_pbk="pbk-b", reality_sni="cloudflare.com"),
        VlessNode(uuid="u1", host="185.1.2.20", port=443, name="A3",
                  reality_pbk="pbk-c", reality_sni="yahoo.com"),
        VlessNode(uuid="u2", host="185.1.2.21", port=443, name="B1",
                  reality_pbk="pbk-d", reality_sni="microsoft.com"),
        VlessNode(uuid="u2", host="185.1.2.21", port=443, name="B2",
                  reality_pbk="pbk-e", reality_sni="yahoo.com"),
    ]
    monkeypatch.setattr(manager_mod.sources, "fetch_igareck_list", lambda: "_fake_")
    monkeypatch.setattr(manager_mod.sources, "fetch_all_sources", lambda **_kw: "_fake_aggregator_")
    monkeypatch.setattr(
        manager_mod.sources, "parse_vless_list", lambda _t: (sample, [])
    )
    monkeypatch.setattr(
        manager_mod.sources, "filter_ru_nodes", lambda ns: (list(ns), [])
    )

    probed_batches: list[list[VlessNode]] = []

    def capturing_probe(self, candidates):
        probed_batches.append(list(candidates))
        for n in candidates:
            n.extra["probe_speed_s"] = 0.5
        return list(candidates)

    monkeypatch.setattr(VlessProxyManager, "_probe_candidates_in_parallel", capturing_probe)

    admitted = pm.refresh_proxy_list()

    # Must have only ONE probe batch — the dedup collapses 5 URIs to 2.
    assert len(probed_batches) == 1
    probed = probed_batches[0]
    probed_keys = {(n.host, n.port) for n in probed}
    assert probed_keys == {("185.1.2.20", 443), ("185.1.2.21", 443)}, (
        f"pre-probe dedup regressed; probe loop saw {len(probed)} entries "
        f"with keys {probed_keys} instead of the 2 unique host:port pairs"
    )
    assert admitted == 2

    # Funnel event must report the suppressed duplicate count.
    events = _load_events(paths["events"])
    refresh_events = [e for e in events if e["event"] == "vless_refresh_start"]
    assert refresh_events
    rfe = refresh_events[-1]
    assert rfe.get("upstream_dups_dropped") == 3, (
        f"expected 3 dropped dups (5 URIs - 2 unique), got "
        f"{rfe.get('upstream_dups_dropped')}"
    )
    assert rfe.get("ru_filtered") == 2  # post-dedup count
    assert rfe.get("candidates") == 2


def test_funnel_recovery_releases_soft_quarantine_when_pool_below_min(
    stub_xray, paths, monkeypatch
) -> None:
    """v1.26 Phase 84.1: candidate-exhaustion recovery.

    When the funnel produces 0 candidates AND the pool is below
    MIN_HEALTHY, soft-quarantined nodes (60s tier) are auto-released
    and the cycle retries once. Hard-quarantined nodes (vpn_detected,
    20-min tier) and 4h repeat-offenders stay locked.

    Pins:
      - Single soft-quarantined host gets released and re-enters the
        candidate set on the same refresh cycle.
      - Hard-quarantined host stays locked and does NOT enter candidates.
    """
    _make_pool(paths["pool"], n=0)
    pm = _manager(paths)

    # Quarantine paths to tmp.
    tmp_q = paths["pool"].parent / "pool_quarantine.json"
    monkeypatch.setattr(manager_mod.quarantine, "QUARANTINE_PATH", str(tmp_q))

    # Pre-populate quarantine: one soft (60s) + one hard (20m).
    import time as _t
    monkeypatch.setattr(_t, "time", lambda: 1000.0)
    manager_mod.quarantine.record_probe_failure(
        "soft.host:443", reason="probe_timeout"  # -> 60s soft tier
    )
    manager_mod.quarantine.record_probe_failure(
        "hard.exit:443", reason="vpn_detected"  # -> 20m hard tier
    )

    # Both nodes appear in the upstream list.
    sample = [
        VlessNode(uuid="u1", host="soft.host", port=443, name="soft",
                  reality_pbk="pbk", reality_sni="microsoft.com"),
        VlessNode(uuid="u2", host="hard.exit", port=443, name="hard",
                  reality_pbk="pbk", reality_sni="microsoft.com"),
    ]
    monkeypatch.setattr(manager_mod.sources, "fetch_igareck_list", lambda: "_")
    monkeypatch.setattr(manager_mod.sources, "fetch_all_sources", lambda **_kw: "_fake_aggregator_")
    monkeypatch.setattr(
        manager_mod.sources, "parse_vless_list", lambda _x: (sample, [])
    )
    monkeypatch.setattr(
        manager_mod.sources, "filter_ru_nodes", lambda ns: (list(ns), [])
    )

    probed_batches: list[list[VlessNode]] = []

    def capturing_probe(self, candidates):
        probed_batches.append(list(candidates))
        for n in candidates:
            n.extra["probe_speed_s"] = 0.5
        return list(candidates)

    monkeypatch.setattr(VlessProxyManager, "_probe_candidates_in_parallel", capturing_probe)

    admitted = pm.refresh_proxy_list()

    # Pool was empty (n=0 < MIN_HEALTHY=10) → soft tier released.
    # Soft host got admitted; hard host stayed locked.
    assert admitted == 1
    assert len(probed_batches) == 1
    probed_hosts = {n.host for n in probed_batches[0]}
    assert probed_hosts == {"soft.host"}, (
        f"recovery released wrong nodes; probed {probed_hosts}"
    )

    # Hard quarantine entry must still exist after the cycle.
    snap = manager_mod.quarantine.snapshot()
    assert "hard.exit:443" in snap["hosts"]
    assert "soft.host:443" not in snap["hosts"]


def test_refresh_drops_cooldown_hosts_before_probe(stub_xray, paths, monkeypatch) -> None:
    _make_pool(paths["pool"], n=0)
    import time as _time

    paths["cooldowns"].parent.mkdir(parents=True, exist_ok=True)
    paths["cooldowns"].write_text(
        json.dumps({"185.1.2.20": {"blocked_at": _time.time() - 60, "reason": "recent"}}),
        encoding="utf-8",
    )
    pm = _manager(paths)

    sample = [
        VlessNode(
            uuid="00000000-0000-0000-0000-000000000001",
            host="185.1.2.20",
            port=443,
            name="cooling",
            reality_pbk="pbk-a",
            reality_sni="sni",
        ),
        VlessNode(
            uuid="00000000-0000-0000-0000-000000000002",
            host="185.1.2.21",
            port=443,
            name="fine",
            reality_pbk="pbk-b",
            reality_sni="sni",
        ),
    ]
    monkeypatch.setattr(manager_mod.sources, "fetch_igareck_list", lambda: "_")
    monkeypatch.setattr(manager_mod.sources, "fetch_all_sources", lambda **_kw: "_fake_aggregator_")
    monkeypatch.setattr(
        manager_mod.sources, "parse_vless_list", lambda _t: (sample, [])
    )
    monkeypatch.setattr(
        manager_mod.sources, "filter_ru_nodes", lambda nodes: (list(nodes), [])
    )

    probed: list[list[VlessNode]] = []

    def fake_probe(self, candidates):
        probed.append(list(candidates))
        for n in candidates:
            n.extra["probe_speed_s"] = 1.0
        return list(candidates)

    monkeypatch.setattr(VlessProxyManager, "_probe_candidates_in_parallel", fake_probe)

    pm.refresh_proxy_list()
    assert probed and {n.host for n in probed[0]} == {"185.1.2.21"}


def test_api_surface_matches_legacy_socks5() -> None:
    legacy = importlib.import_module("proxy_manager").ProxyManager

    def public_members(cls) -> dict[str, inspect.Signature]:
        members = {}
        for name, obj in inspect.getmembers(cls):
            if name.startswith("_"):
                continue
            if not callable(obj):
                continue
            try:
                members[name] = inspect.signature(obj)
            except (TypeError, ValueError):
                continue
        return members

    legacy_members = public_members(legacy)
    new_members = public_members(VlessProxyManager)

    missing: list[str] = [m for m in legacy_members if m not in new_members]
    assert not missing, f"VlessProxyManager is missing legacy methods: {missing}"

    # Arity must match for each shared method so positional callers keep working.
    for name, legacy_sig in legacy_members.items():
        new_sig = new_members[name]
        legacy_required = _required_positionals(legacy_sig)
        new_required = _required_positionals(new_sig)
        assert new_required == legacy_required, (
            f"method {name} changed required-positional arity: "
            f"legacy={legacy_required} new={new_required}"
        )


def test_atomic_pool_write_survives_partial_failure(stub_xray, paths, monkeypatch) -> None:
    _make_pool(paths["pool"], n=2)
    pm = _manager(paths)
    original = paths["pool"].read_text(encoding="utf-8")

    real_replace = os.replace

    def explode_on_replace(*_a, **_kw):
        raise RuntimeError("disk full simulation")

    monkeypatch.setattr(manager_mod.pool_state.os, "replace", explode_on_replace)
    with pytest.raises(RuntimeError):
        pm._remove_host_and_restart("185.1.2.10", reason="explosion-test")  # noqa: SLF001

    # Restore os.replace so subsequent tests are unaffected.
    monkeypatch.setattr(manager_mod.pool_state.os, "replace", real_replace)

    # The on-disk pool file must be unchanged since the atomic swap failed.
    assert paths["pool"].read_text(encoding="utf-8") == original


def test_xray_status_reflects_running_state(stub_xray, paths) -> None:
    _make_pool(paths["pool"], n=2)
    pm = _manager(paths)
    status = pm.xray_status()
    assert status["running"] is False
    assert status["pool_size"] == 2

    pm.get_working_proxy(allow_refresh=False)
    status = pm.xray_status()
    assert status["running"] is True
    assert status["pool_size"] == 2
    assert status["inbound_port"] == 10808


def test_shutdown_stops_running_xray(stub_xray, paths) -> None:
    _make_pool(paths["pool"], n=2)
    pm = _manager(paths)
    pm.get_working_proxy(allow_refresh=False)
    inst = stub_xray.instances[-1]
    assert inst.is_running()
    pm._shutdown()  # noqa: SLF001 — simulates atexit hook
    assert not inst.is_running()
    assert inst._stopped >= 1


def test_get_event_stats_matches_legacy_shape(stub_xray, paths) -> None:
    # Write a couple of sample events in the new schema and one legacy one.
    paths["events"].parent.mkdir(parents=True, exist_ok=True)
    lines = [
        {"ts": "2026-04-22T23:00:00", "event": "vless_node_admitted", "host": "1.1.1.1"},
        {"ts": "2026-04-22T23:00:01", "event": "vless_refresh_start", "candidates": 4},
        {"ts": "2026-04-22T23:00:02", "event": "vless_node_removed", "host": "1.1.1.2"},
        {"ts": "2026-04-22T23:00:03", "event": "found", "addr": "1.1.1.3:443"},
    ]
    paths["events"].write_text(
        "\n".join(json.dumps(e) for e in lines) + "\n", encoding="utf-8"
    )
    # Patch the module-level EVENTS_FILE so the @staticmethod reads from our tmp file.
    original = manager_mod.EVENTS_FILE
    manager_mod.EVENTS_FILE = paths["events"]
    try:
        stats = VlessProxyManager.get_event_stats()
    finally:
        manager_mod.EVENTS_FILE = original
    assert set(stats["periods"].keys()) == {"today", "week", "month"}
    for period in stats["periods"].values():
        assert set(period.keys()) >= {"found", "removed", "refresh", "success_rate"}


def test_get_event_stats_handles_mixed_naive_and_aware_timestamps(stub_xray, paths) -> None:
    """v1.26 regression: proxy_events.jsonl grew to mix two timestamp
    formats on EC2 — legacy naive (``datetime.now().isoformat()`` from
    _track_event) and aware UTC (``+00:00`` suffix emitted by
    scheduler_service + scraper-pause hooks). Subtracting a naive
    ``datetime.now()`` from an aware timestamp raised TypeError inside
    the per-line try/except, silently swallowing every event on EC2.
    Result: admin dashboard showed "Нет данных" even with 80k+ events.

    Fix: normalise aware -> naive by dropping tzinfo before subtraction.
    This test pins both formats getting counted. Intentionally timestamps
    events in the very recent past so they land in the ``today`` bucket
    regardless of when the test runs.
    """
    from datetime import datetime, timedelta, timezone

    paths["events"].parent.mkdir(parents=True, exist_ok=True)
    recent_naive = (datetime.now() - timedelta(minutes=5)).isoformat()
    recent_aware = (
        datetime.now(timezone.utc) - timedelta(minutes=5)
    ).isoformat()  # trailing '+00:00'

    lines = [
        {"ts": recent_naive, "event": "vless_node_admitted", "host": "1.1.1.1"},
        {"ts": recent_naive, "event": "vless_refresh_start", "candidates": 5},
        {"ts": recent_aware, "event": "vless_node_admitted", "host": "2.2.2.2"},
        {"ts": recent_aware, "event": "vless_node_removed", "host": "1.1.1.1"},
        {"ts": recent_aware, "event": "test_fail", "host": "3.3.3.3"},
    ]
    paths["events"].write_text(
        "\n".join(json.dumps(e) for e in lines) + "\n", encoding="utf-8"
    )

    original = manager_mod.EVENTS_FILE
    manager_mod.EVENTS_FILE = paths["events"]
    try:
        stats = VlessProxyManager.get_event_stats()
    finally:
        manager_mod.EVENTS_FILE = original

    today = stats["periods"]["today"]
    # Both naive+aware admissions must count, not just one.
    assert today["found"] == 2, (
        f"expected 2 admissions, got {today['found']} — tz-mix regressed"
    )
    assert today["removed"] == 1
    assert today["refresh"] == 1
    assert today["test_fail"] == 1
    # success_rate = found / (found + test_fail) = 2 / 3 = 66.7
    assert today["success_rate"] == 66.7


# ── Live integration test ────────────────────────────────────


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("RUN_LIVE") != "1",
    reason="Live VLESS manager tests are gated on RUN_LIVE=1",
)
def test_live_vless_end_to_end(tmp_path: Path) -> None:
    """Full refresh → xray restart → vkusvill probe round-trip."""
    from vless import installer

    installer.install()
    pm = VlessProxyManager(
        pool_path=tmp_path / "vless_pool.json",
        cooldowns_path=tmp_path / "cooldowns.json",
        events_path=tmp_path / "events.jsonl",
        xray_config_path=tmp_path / "active.json",
        xray_log_path=tmp_path / "xray.log",
        register_atexit=False,
    )
    try:
        admitted = pm.refresh_proxy_list()
        assert admitted >= 1, f"refresh admitted only {admitted} nodes"
        proxy = pm.get_working_proxy(allow_refresh=False)
        assert proxy == "127.0.0.1:10808"
        assert pm.xray_status()["running"] is True
    finally:
        pm._shutdown()  # noqa: SLF001


# ── utils ────────────────────────────────────────────────────


def _required_positionals(sig: inspect.Signature) -> int:
    n = 0
    for p in sig.parameters.values():
        if p.name == "self":
            continue
        if p.kind not in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.POSITIONAL_ONLY,
        ):
            continue
        if p.default is inspect.Parameter.empty:
            n += 1
    return n


def _load_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def test_pool_state_roundtrip_preserves_tls_fields(tmp_path) -> None:
    """Regression: security / tls_sni / tls_allow_insecure must survive save→load.

    Prior to this check, the pool file dropped those fields so TLS nodes
    came back as Reality with an empty public key, causing xray to emit a
    Reality outbound that could never complete its handshake.
    """
    from vless import pool_state

    tls_node = VlessNode(
        uuid="75807638-6f19-07d0-ae08-38492ee85c88",
        host="5.178.87.140",
        port=52006,
        name="\U0001f1f7\U0001f1fa Russia [*CIDR]",
        flow="xtls-rprx-vision",
        transport="tcp",
        encryption="none",
        header_type="none",
        security="tls",
        tls_sni="cluster-russia-1.firstvideocdn.ru",
        tls_allow_insecure=True,
    )
    reality_node = VlessNode(
        uuid="4036688f-4e87-502d-82e0-3f0203a6f004",
        host="94.103.2.194",
        port=443,
        name="reality-sample",
        reality_pbk="CxSsLf7XPhNjhqp0QBOI699kkudkiJCoCVfqqXSllyU",
        reality_sni="business.max.ru",
        reality_sid="18ec",
        security="reality",
    )

    pool = pool_state.replace_nodes({"updated_at": None, "nodes": []}, [tls_node, reality_node])
    pool_path = tmp_path / "vless_pool.json"
    pool_state.save(pool, pool_path)

    reloaded = pool_state.load(pool_path)
    nodes = pool_state.nodes_from(reloaded)

    by_host = {n.host: n for n in nodes}
    assert by_host["5.178.87.140"].security == "tls"
    assert by_host["5.178.87.140"].tls_sni == "cluster-russia-1.firstvideocdn.ru"
    assert by_host["5.178.87.140"].tls_allow_insecure is True
    assert by_host["94.103.2.194"].security == "reality"
    assert by_host["94.103.2.194"].reality_pbk != ""


# Silence Iterable "unused" in non-type-check runs.
_ = Iterable


def test_filter_ru_nodes_rejects_anything_without_explicit_ru_marker(monkeypatch: pytest.MonkeyPatch) -> None:
    """v1.26 Phase 84.4: require an EXPLICIT 🇷🇺 / "russia" marker.

    Phase 84.2 (the predecessor to this test) admitted unlabeled lines
    via "let the egress probe decide." Live evidence on EC2 (2026-05-14)
    showed the kort0881 / SoliSpirit aggregators ship hundreds of nodes
    with handle-style labels (#Join+Telegram:@Farah_VPN) or no flag at
    all, of which the vast majority are dead Azure exits or non-RU
    egresses. Probing ~180 candidates per cycle resulted in 0 admissions
    because the budget got eaten by garbage. Phase 84.4 reverts to
    explicit-RU-only — the egress probe is still the source of truth
    but we no longer waste xray-startup budget on label-evidence-free
    candidates.

    Net trade-off: ~140 unlabeled candidates dropped per cycle, of which
    some were genuinely RU. We can re-enable the fallthrough behind a
    feature flag if the pool starves; the helper
    ``_has_explicit_non_ru_marker`` and the related constants are
    intentionally retained in ``vless.sources`` for that path.
    """
    from vless import sources as _sources
    nodes = [
        VlessNode(uuid="u1", host="1.1.1.1", port=443, name="🇷🇺 Russia [*CIDR]",
                  reality_pbk="pbk", reality_sni="x.com"),
        VlessNode(uuid="u2", host="2.2.2.2", port=443, name="🇫🇮 Finland",
                  reality_pbk="pbk", reality_sni="x.com"),
        VlessNode(uuid="u3", host="3.3.3.3", port=443, name="🇩🇪 [DE] premium",
                  reality_pbk="pbk", reality_sni="x.com"),
        VlessNode(uuid="u4", host="4.4.4.4", port=443, name="Join+Telegram:@Farah_VPN",
                  reality_pbk="pbk", reality_sni="x.com"),
        VlessNode(uuid="u5", host="5.5.5.5", port=443, name="",
                  reality_pbk="pbk", reality_sni="x.com"),
        VlessNode(uuid="u6", host="6.6.6.6", port=443, name="russia premium",
                  reality_pbk="pbk", reality_sni="x.com"),
    ]
    accepted, rejected = _sources.filter_ru_nodes(nodes)
    accepted_hosts = {n.host for n in accepted}
    rejected_hosts = {n.host for n in rejected}
    # ONLY explicit-RU markers (emoji or "russia" text) admit.
    assert accepted_hosts == {"1.1.1.1", "6.6.6.6"}
    # Explicit non-RU AND unlabeled both drop at the label gate.
    assert rejected_hosts == {"2.2.2.2", "3.3.3.3", "4.4.4.4", "5.5.5.5"}


def test_parse_vless_list_decodes_html_entity_ampersands(stub_xray, paths) -> None:
    """v1.26 Phase 84.2: SoliSpirit and similar exporters use `&amp;` as
    query separators. Pin that the parser decodes them so the URI's
    query params are correctly split.
    """
    encoded = (
        "vless://4371ad14-b981-4699-bedf-83fb79bde3e6"
        "@176.108.242.76:443"
        "?security=reality&amp;encryption=none"
        "&amp;pbk=FkmYFobwxLMLEktYXywmjthuEYCZggITsxwPNasTKUg"
        "&amp;flow=xtls-rprx-vision&amp;sni=www.vkvideo.ru"
        "&amp;sid=6354585c37827955"
        "#🇷🇺 Russia"
    )
    from vless import parser
    nodes, errors = parser.parse_vless_list(encoded)
    assert errors == [], f"unexpected parse errors: {errors}"
    assert len(nodes) == 1
    n = nodes[0]
    assert n.host == "176.108.242.76"
    assert n.port == 443
    assert n.security == "reality"
    assert n.reality_pbk == "FkmYFobwxLMLEktYXywmjthuEYCZggITsxwPNasTKUg"
    assert n.reality_sni == "www.vkvideo.ru"
    assert n.flow == "xtls-rprx-vision"


def test_fetch_all_sources_unions_igareck_and_extras(monkeypatch: pytest.MonkeyPatch) -> None:
    """v1.26 Phase 84.2: fetch_all_sources concatenates igareck + extras.

    Verifies the contract:
      1. igareck output included.
      2. Each extra source URL fetched independently.
      3. Per-source failure tolerated; remaining sources still contribute.
      4. ALL sources failing re-raises.
    """
    from vless import sources

    monkeypatch.setattr(sources, "fetch_igareck_list", lambda **_: "IGARECK_BLOCK")

    fetched_urls: list[str] = []
    def _fake_one(url, *, timeout):
        fetched_urls.append(url)
        if "soli" in url.lower():
            raise OSError("simulated 404 on SoliSpirit")
        # Use the basename so the assertion matcher is precise.
        basename = url.rsplit("/", 1)[-1]
        return f"BODY_{basename}"

    monkeypatch.setattr(sources, "_fetch_one", _fake_one)

    blob = sources.fetch_all_sources(
        extra_urls=(
            "https://example.com/list-a.txt",
            "https://example.com/SoliSpirit/Russia.txt",
            "https://example.com/list-b.txt",
        ),
        timeout=1.0,
    )

    # igareck block is in.
    assert "IGARECK_BLOCK" in blob
    # Two non-failing extras are in.
    assert "BODY_list-a.txt" in blob
    assert "BODY_list-b.txt" in blob
    # Failing extra dropped silently, didn't break the union.
    assert "BODY_Russia.txt" not in blob
    # All three extra URLs were attempted.
    assert len(fetched_urls) == 3

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

    def __init__(self, *args, **kwargs) -> None:
        self.config_path = Path(kwargs["config_path"])
        self.log_path = Path(kwargs.get("log_path") or self.config_path.with_suffix(".log"))
        self._binary = kwargs.get("binary")
        self._running = False
        self._started = 0
        self._stopped = 0
        self._restarted = 0
        self._writes = 0
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
            "fetch_igareck_list called from a unit test — monkeypatch it explicitly"
        )

    def _geo_tripwire(*_a, **_kw):
        raise AssertionError(
            "filter_ru_nodes called from a unit test — monkeypatch it explicitly"
        )

    monkeypatch.setattr(manager_mod.sources, "fetch_igareck_list", _network_tripwire)
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


def test_remove_proxy_with_local_endpoint_is_noop(stub_xray, paths) -> None:
    _make_pool(paths["pool"], n=3)
    pm = _manager(paths)
    pm.remove_proxy("127.0.0.1:10808")
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


# Silence Iterable "unused" in non-type-check runs.
_ = Iterable

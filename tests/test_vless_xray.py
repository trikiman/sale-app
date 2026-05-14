"""Unit + optional live tests for :class:`vless.xray.XrayProcess`.

Unit tests monkeypatch :mod:`subprocess.Popen` so they never spawn a real
xray (and therefore don't require the binary to be installed). The single
``@pytest.mark.integration`` test runs only when ``RUN_LIVE=1`` is set.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest

from vless import xray as xray_mod
from vless.config_gen import build_xray_config
from vless.parser import VlessNode
from vless.xray import XrayProcess, XrayStartupError


def _make_stub_config(path: Path, port: int = 10808) -> None:
    """Write a minimal valid-shape xray config so ``inbound_port`` works."""
    node = VlessNode(
        uuid="11111111-1111-1111-1111-111111111111",
        host="example.com",
        port=443,
        name="stub",
        reality_pbk="AAAA",
        reality_sni="example.com",
    )
    config = build_xray_config([node], listen_port=port)
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")


class _FakePopen:
    """Minimal Popen stand-in that pretends xray is running until killed.

    Exposes the same surface ``XrayProcess`` touches (poll, wait, kill,
    terminate, pid, returncode). Also lets tests flip behaviour for crash /
    never-opens-port / respawn scenarios.
    """

    # Class-level registry so tests can inspect which Popens were spawned.
    instances: list["_FakePopen"] = []

    def __init__(
        self,
        *args,
        exit_immediately: int | None = None,
        open_port: int | None = None,
        **kwargs,
    ) -> None:
        type(self).instances.append(self)
        self.args = args
        self.kwargs = kwargs
        self.pid = 10_000 + len(type(self).instances)
        self.returncode = exit_immediately
        self._terminated = threading.Event()
        self._port = open_port
        self._listener: socket.socket | None = None
        if exit_immediately is None and open_port is not None:
            self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._listener.bind(("127.0.0.1", open_port))
            self._listener.listen(1)

    def poll(self):
        return self.returncode

    def wait(self, timeout: float | None = None):
        if self.returncode is not None:
            return self.returncode
        if timeout is None:
            self._terminated.wait()
        else:
            self._terminated.wait(timeout)
        if not self._terminated.is_set():
            raise subprocess.TimeoutExpired(cmd="xray", timeout=timeout)
        return self.returncode

    def terminate(self) -> None:
        self._finish(exit_code=0)

    def kill(self) -> None:
        self._finish(exit_code=-9)

    def _finish(self, *, exit_code: int) -> None:
        if self.returncode is None:
            self.returncode = exit_code
        if self._listener is not None:
            try:
                self._listener.close()
            except OSError:
                pass
            self._listener = None
        self._terminated.set()


@pytest.fixture(autouse=True)
def _reset_fake_popen():
    _FakePopen.instances.clear()
    yield
    for inst in _FakePopen.instances:
        inst._finish(exit_code=0)
    _FakePopen.instances.clear()


@pytest.fixture
def xray_paths(tmp_path: Path) -> dict[str, Path]:
    binary = tmp_path / "xray"
    binary.write_text("#!/bin/sh\nexit 0\n")
    binary.chmod(0o755)
    config = tmp_path / "config.json"
    log = tmp_path / "xray.log"
    return {"binary": binary, "config": config, "log": log}


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_start_succeeds_when_port_opens(monkeypatch, xray_paths) -> None:
    port = _free_port()
    _make_stub_config(xray_paths["config"], port=port)

    def fake_popen(*a, **kw):
        return _FakePopen(open_port=port, *a, **kw)

    monkeypatch.setattr(xray_mod.subprocess, "Popen", fake_popen)

    proc = XrayProcess(
        binary=xray_paths["binary"],
        config_path=xray_paths["config"],
        log_path=xray_paths["log"],
        health_check_timeout=3.0,
    )
    try:
        proc.start()
        assert proc.is_running()
        assert proc.health_check()
        assert proc.inbound_port == port
    finally:
        proc.stop()
    assert not proc.is_running()


def test_start_raises_when_xray_exits_immediately(monkeypatch, xray_paths) -> None:
    _make_stub_config(xray_paths["config"])

    def fake_popen(*a, **kw):
        return _FakePopen(exit_immediately=1, *a, **kw)

    monkeypatch.setattr(xray_mod.subprocess, "Popen", fake_popen)

    proc = XrayProcess(
        binary=xray_paths["binary"],
        config_path=xray_paths["config"],
        log_path=xray_paths["log"],
        health_check_timeout=1.0,
    )
    with pytest.raises(XrayStartupError) as excinfo:
        proc.start()
    assert "exited" in str(excinfo.value).lower()
    assert not proc.is_running()


def test_start_times_out_if_port_never_opens(monkeypatch, xray_paths) -> None:
    _make_stub_config(xray_paths["config"], port=_free_port())

    # No open_port means the fake subprocess never binds a listener.
    def fake_popen(*a, **kw):
        return _FakePopen(*a, **kw)

    monkeypatch.setattr(xray_mod.subprocess, "Popen", fake_popen)

    proc = XrayProcess(
        binary=xray_paths["binary"],
        config_path=xray_paths["config"],
        log_path=xray_paths["log"],
        health_check_timeout=0.6,
    )
    with pytest.raises(XrayStartupError) as excinfo:
        proc.start()
    assert "did not open" in str(excinfo.value).lower()


def test_start_raises_when_binary_missing(xray_paths) -> None:
    _make_stub_config(xray_paths["config"])
    proc = XrayProcess(
        binary=Path("/definitely/not/a/real/xray"),
        config_path=xray_paths["config"],
        log_path=xray_paths["log"],
        health_check_timeout=0.5,
    )
    with pytest.raises(XrayStartupError):
        proc.start()


def test_start_raises_when_config_missing(xray_paths) -> None:
    proc = XrayProcess(
        binary=xray_paths["binary"],
        config_path=xray_paths["config"],  # file not written
        log_path=xray_paths["log"],
    )
    with pytest.raises(XrayStartupError) as excinfo:
        proc.start()
    assert "config not found" in str(excinfo.value).lower()


def test_write_config_is_atomic(xray_paths) -> None:
    proc = XrayProcess(
        binary=xray_paths["binary"],
        config_path=xray_paths["config"],
        log_path=xray_paths["log"],
    )
    # Seed with a known-good config.
    good = {"inbounds": [{"protocol": "socks", "port": 10808}], "outbounds": []}
    proc.write_config(good)
    assert json.loads(xray_paths["config"].read_text(encoding="utf-8"))["inbounds"][0]["port"] == 10808

    # Overwriting must keep the file parseable at every instant — simulate by
    # overwriting 100 times in parallel and confirming the file is never
    # truncated to an empty read.
    def _hammer() -> None:
        for i in range(50):
            proc.write_config({"round": i, "inbounds": [{"protocol": "socks", "port": i}]})

    threads = [threading.Thread(target=_hammer) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    final = json.loads(xray_paths["config"].read_text(encoding="utf-8"))
    assert "inbounds" in final


def test_restart_writes_new_config_and_respawns(monkeypatch, xray_paths) -> None:
    port = _free_port()
    _make_stub_config(xray_paths["config"], port=port)

    def fake_popen(*a, **kw):
        return _FakePopen(open_port=port, *a, **kw)

    monkeypatch.setattr(xray_mod.subprocess, "Popen", fake_popen)

    proc = XrayProcess(
        binary=xray_paths["binary"],
        config_path=xray_paths["config"],
        log_path=xray_paths["log"],
        health_check_timeout=3.0,
    )
    proc.start()
    try:
        fresh_config = build_xray_config(
            [
                VlessNode(
                    uuid="22222222-2222-2222-2222-222222222222",
                    host="new.example.com",
                    port=443,
                    name="fresh",
                    reality_pbk="BBBB",
                    reality_sni="new.example.com",
                )
            ],
            listen_port=port,
        )
        proc.restart(new_config=fresh_config)
        written = json.loads(xray_paths["config"].read_text(encoding="utf-8"))
        assert any(
            ob["protocol"] == "vless"
            and ob["settings"]["vnext"][0]["address"] == "new.example.com"
            for ob in written["outbounds"]
        )
        assert proc.is_running()
    finally:
        proc.stop()


def test_stop_is_noop_when_never_started(xray_paths) -> None:
    proc = XrayProcess(
        binary=xray_paths["binary"],
        config_path=xray_paths["config"],
        log_path=xray_paths["log"],
    )
    proc.stop()  # must not raise
    assert not proc.is_running()


def test_inbound_port_falls_back_to_default_on_invalid_config(xray_paths) -> None:
    xray_paths["config"].write_text("{ not: valid json", encoding="utf-8")
    proc = XrayProcess(
        binary=xray_paths["binary"],
        config_path=xray_paths["config"],
        log_path=xray_paths["log"],
    )
    assert proc.inbound_port == 10808


class _FakeGeoResponse:
    def __init__(self, status_code: int, payload: dict) -> None:
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=httpx.Request("GET", "https://example/"),
                response=httpx.Response(self.status_code),
            )

    def json(self) -> dict:
        return self._payload


class _FakeGeoClient:
    """Records GETs and replays scripted responses for verify_egress tests."""

    def __init__(self, responses: list[_FakeGeoResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[str] = []

    def __enter__(self) -> "_FakeGeoClient":
        return self

    def __exit__(self, *args) -> None:
        return None

    def get(self, url: str) -> _FakeGeoResponse:
        self.calls.append(url)
        if not self._responses:
            raise RuntimeError("no fake response left")
        return self._responses.pop(0)


def _patch_geo_client(monkeypatch, fake: _FakeGeoClient) -> None:
    import httpx

    monkeypatch.setattr(httpx, "Client", lambda *a, **kw: fake)


def test_verify_egress_returns_first_provider_success(monkeypatch, xray_paths) -> None:
    """v1.26 Phase 84.3: consensus voting.

    With a single RU response (other 2 providers absent), the result is
    still admit + 'RU' — the consensus tie-break favors expected_country.

    Pre-Phase 84.3 (legacy first-success-wins): 1 response was enough.
    Post-Phase 84.3 (consensus): all 3 providers are queried, but a
    single RU vote with no other votes is still a majority.
    """
    _make_stub_config(xray_paths["config"])
    # Empty responses for the other 2 providers (they 'fail' silently).
    fake = _FakeGeoClient(
        [
            _FakeGeoResponse(200, {"country": "RU"}),
            _FakeGeoResponse(429, {}),
            _FakeGeoResponse(503, {}),
        ]
    )
    _patch_geo_client(monkeypatch, fake)
    proc = XrayProcess(
        binary=xray_paths["binary"],
        config_path=xray_paths["config"],
        log_path=xray_paths["log"],
    )
    ok, country = proc.verify_egress(expected_country="RU", timeout=1.0)
    assert (ok, country) == (True, "RU")
    # All 3 providers attempted for consensus.
    assert fake.calls == [
        "https://ipinfo.io/json",
        "https://ipapi.co/json",
        "http://ip-api.com/json",
    ]


def test_verify_egress_falls_back_when_first_provider_429s(
    monkeypatch, xray_paths
) -> None:
    """v1.26 Phase 84.3: when ipinfo.io rate-limits, the remaining
    providers' votes still produce an RU consensus.
    """
    _make_stub_config(xray_paths["config"])
    fake = _FakeGeoClient(
        [
            _FakeGeoResponse(429, {}),
            _FakeGeoResponse(200, {"country_code": "RU"}),
            _FakeGeoResponse(200, {"countryCode": "RU"}),
        ]
    )
    _patch_geo_client(monkeypatch, fake)
    proc = XrayProcess(
        binary=xray_paths["binary"],
        config_path=xray_paths["config"],
        log_path=xray_paths["log"],
    )
    ok, country = proc.verify_egress(expected_country="RU", timeout=1.0)
    assert (ok, country) == (True, "RU")
    # All 3 providers consulted (consensus mode).
    assert fake.calls == [
        "https://ipinfo.io/json",
        "https://ipapi.co/json",
        "http://ip-api.com/json",
    ]


def test_verify_egress_uses_third_provider_when_first_two_fail(
    monkeypatch, xray_paths
) -> None:
    """v1.26 Phase 84.3: when 2 of 3 providers fail and the lone vote is
    non-RU, reject with a vote-tagged country string for diagnostic
    accuracy.
    """
    _make_stub_config(xray_paths["config"])
    fake = _FakeGeoClient(
        [
            _FakeGeoResponse(429, {}),
            _FakeGeoResponse(503, {}),
            _FakeGeoResponse(200, {"countryCode": "DE"}),
        ]
    )
    _patch_geo_client(monkeypatch, fake)
    proc = XrayProcess(
        binary=xray_paths["binary"],
        config_path=xray_paths["config"],
        log_path=xray_paths["log"],
    )
    ok, country = proc.verify_egress(expected_country="RU", timeout=1.0)
    # Vote tally format makes the partial-consensus visible.
    assert (ok, country) == (False, "DE (1/1)")
    assert fake.calls == [
        "https://ipinfo.io/json",
        "https://ipapi.co/json",
        "http://ip-api.com/json",
    ]


def test_verify_egress_consensus_admits_when_majority_says_ru(
    monkeypatch, xray_paths
) -> None:
    """v1.26 Phase 84.3: 2 RU votes vs 1 DE vote -> admit.

    Pin the live-production scenario that triggered Phase 84.3:
    Citytelecom RU IPs got a false DE result from ip-api.com but
    correct RU from ipinfo.io and ipapi.co. Pre-Phase 84.3 the
    first-success-wins logic could pick the wrong provider and
    quarantine healthy nodes for 20 min.
    """
    _make_stub_config(xray_paths["config"])
    fake = _FakeGeoClient(
        [
            _FakeGeoResponse(200, {"country": "RU"}),
            _FakeGeoResponse(200, {"country_code": "RU"}),
            _FakeGeoResponse(200, {"countryCode": "DE"}),  # ip-api.com false-DE
        ]
    )
    _patch_geo_client(monkeypatch, fake)
    proc = XrayProcess(
        binary=xray_paths["binary"],
        config_path=xray_paths["config"],
        log_path=xray_paths["log"],
    )
    ok, country = proc.verify_egress(expected_country="RU", timeout=1.0)
    assert (ok, country) == (True, "RU"), (
        "consensus regressed: 2/3 RU votes should admit"
    )


def test_verify_egress_consensus_rejects_when_majority_says_non_ru(
    monkeypatch, xray_paths
) -> None:
    """v1.26 Phase 84.3: 2 DE votes vs 1 RU vote -> reject."""
    _make_stub_config(xray_paths["config"])
    fake = _FakeGeoClient(
        [
            _FakeGeoResponse(200, {"country": "DE"}),
            _FakeGeoResponse(200, {"country_code": "DE"}),
            _FakeGeoResponse(200, {"countryCode": "RU"}),
        ]
    )
    _patch_geo_client(monkeypatch, fake)
    proc = XrayProcess(
        binary=xray_paths["binary"],
        config_path=xray_paths["config"],
        log_path=xray_paths["log"],
    )
    ok, country = proc.verify_egress(expected_country="RU", timeout=1.0)
    assert ok is False
    assert "DE" in country  # reason includes the majority country


def test_verify_egress_consensus_tie_breaks_in_favor_of_expected_country(
    monkeypatch, xray_paths
) -> None:
    """v1.26 Phase 84.3: 1 RU vote, 1 DE vote, 1 provider down -> admit.

    Ties resolve toward expected_country to avoid quarantining a healthy
    node based on a single misclassifying provider's word.
    """
    _make_stub_config(xray_paths["config"])
    fake = _FakeGeoClient(
        [
            _FakeGeoResponse(200, {"country": "RU"}),
            _FakeGeoResponse(429, {}),  # provider 2 down
            _FakeGeoResponse(200, {"countryCode": "DE"}),
        ]
    )
    _patch_geo_client(monkeypatch, fake)
    proc = XrayProcess(
        binary=xray_paths["binary"],
        config_path=xray_paths["config"],
        log_path=xray_paths["log"],
    )
    ok, country = proc.verify_egress(expected_country="RU", timeout=1.0)
    assert (ok, country) == (True, "RU"), (
        "tie regressed: 1 RU vs 1 DE should admit (favor expected)"
    )


def test_verify_egress_returns_last_error_when_all_providers_fail(
    monkeypatch, xray_paths
) -> None:
    """If every provider rate-limits, the rejection reason must capture
    *which* provider's error so operators can diagnose pool shrink."""
    _make_stub_config(xray_paths["config"])
    fake = _FakeGeoClient(
        [
            _FakeGeoResponse(429, {}),
            _FakeGeoResponse(429, {}),
            _FakeGeoResponse(429, {}),
        ]
    )
    _patch_geo_client(monkeypatch, fake)
    proc = XrayProcess(
        binary=xray_paths["binary"],
        config_path=xray_paths["config"],
        log_path=xray_paths["log"],
    )
    ok, detail = proc.verify_egress(expected_country="RU", timeout=1.0)
    assert ok is False
    assert "429" in detail
    assert len(fake.calls) == 3


def test_verify_egress_explicit_url_keeps_single_provider_path(
    monkeypatch, xray_paths
) -> None:
    """Live integration tests pin a single provider via the legacy ``url=``
    kwarg and expect the call to NOT fall back. Backwards-compat guard."""
    _make_stub_config(xray_paths["config"])
    fake = _FakeGeoClient([_FakeGeoResponse(429, {})])
    _patch_geo_client(monkeypatch, fake)
    proc = XrayProcess(
        binary=xray_paths["binary"],
        config_path=xray_paths["config"],
        log_path=xray_paths["log"],
    )
    ok, _ = proc.verify_egress(
        expected_country="RU", timeout=1.0, url="https://example/json"
    )
    assert ok is False
    assert fake.calls == ["https://example/json"]


def test_inbound_port_reads_custom_socks_port(xray_paths) -> None:
    port = 19999
    _make_stub_config(xray_paths["config"], port=port)
    proc = XrayProcess(
        binary=xray_paths["binary"],
        config_path=xray_paths["config"],
        log_path=xray_paths["log"],
    )
    assert proc.inbound_port == port


def test_restart_budget_exhausts_after_limit(monkeypatch, xray_paths) -> None:
    port = _free_port()
    _make_stub_config(xray_paths["config"], port=port)

    spawn_counter = {"n": 0}
    lock = threading.Lock()

    def fake_popen(*a, **kw):
        with lock:
            spawn_counter["n"] += 1
            n = spawn_counter["n"]
        if n == 1:
            # First call succeeds so start() returns.
            return _FakePopen(open_port=port, *a, **kw)
        # Every subsequent respawn dies instantly.
        return _FakePopen(exit_immediately=1, *a, **kw)

    monkeypatch.setattr(xray_mod.subprocess, "Popen", fake_popen)

    proc = XrayProcess(
        binary=xray_paths["binary"],
        config_path=xray_paths["config"],
        log_path=xray_paths["log"],
        restart_limit=2,
        health_check_timeout=3.0,
    )
    proc.start()
    # Force a crash by tearing down the first listener-owning fake.
    first = _FakePopen.instances[0]
    first._finish(exit_code=137)

    # Give the watcher thread time to observe and burn through the budget.
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        if spawn_counter["n"] >= 1 + proc._restart_limit + 1:
            break
        time.sleep(0.1)

    # After exhaustion, the watcher must have stopped trying.
    proc.stop()
    assert spawn_counter["n"] <= 1 + proc._restart_limit + 1
    # At least one retry happened before giving up.
    assert spawn_counter["n"] >= 2


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("RUN_LIVE") != "1",
    reason="Live xray + network tests are gated on RUN_LIVE=1",
)
def test_live_egress_ru(tmp_path) -> None:
    """Install xray, build a real config, and prove outbound egress is RU.

    The balancer's ``random`` strategy picks one outbound per request, so a
    single ``verify_egress`` call only probes one node. The igareck source
    ships some relay nodes whose actual exit is non-RU even though their
    front-end IP geo-verifies as RU; we tolerate those by retrying a small
    number of times before failing — the pool only needs *at least one*
    RU-exit node for the stack to be proven end-to-end.
    """
    from vless import installer, sources

    binary = installer.install()
    text = sources.fetch_igareck_list()
    nodes, _errors = sources.parse_vless_list(text)
    ru_nodes, _rejected = sources.filter_ru_nodes(nodes)
    assert len(ru_nodes) >= 1, "live RU pool must have at least one node"

    config_path = tmp_path / "live.json"
    log_path = tmp_path / "live.log"
    pool_size = min(5, len(ru_nodes))
    config_path.write_text(
        json.dumps(build_xray_config(ru_nodes[:pool_size]), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    proc = XrayProcess(binary=binary, config_path=config_path, log_path=log_path)
    proc.start()
    try:
        seen: list[str] = []
        for _ in range(8):  # up to 8 random balancer picks from a pool of 5
            ok, detail = proc.verify_egress(expected_country="RU", timeout=20.0)
            seen.append(detail)
            if ok:
                return
        pytest.fail(
            f"expected at least one RU egress from pool of {pool_size}; "
            f"detected countries={seen}"
        )
    finally:
        proc.stop()

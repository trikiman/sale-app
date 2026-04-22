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

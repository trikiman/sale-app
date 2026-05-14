"""v1.21 Phase 68 — xray auto-reload on admission change.

Covers:
  * ``_extract_running_hosts`` — reads the running xray config's outbound host set
  * ``_reload_xray_systemd`` — throttle, Windows skip, failure path
  * ``refresh_proxy_list`` wiring — no reload when admission set unchanged,
    reload + ``pool_refresh_complete`` event when it differs

Unit-only (no subprocess, no real systemd). Live verification via
``scripts/verify_v1.21.sh 68`` + ``68-VERIFICATION.md`` NEEDS_OPERATOR steps.
"""
from __future__ import annotations

import json
import sys

import pytest

from vless.manager import (
    SYSTEMCTL_ARGS,
    VlessProxyManager,
    XRAY_RESTART_THROTTLE_S,
    XRAY_RESTART_TIMEOUT_S,
)


@pytest.fixture
def pm(tmp_path, monkeypatch):
    """VlessProxyManager with isolated pool/cooldown/events/xray-config state."""
    pool_path = tmp_path / "vless_pool.json"
    pool_path.write_text(
        '{"nodes": [{"host": "1.2.3.4", "port": 443}], '
        '"updated_at": "2026-05-12T00:00:00"}'
    )
    cooldowns_path = tmp_path / "cooldowns.json"
    cooldowns_path.write_text("{}")
    events_path = tmp_path / "events.jsonl"
    xray_cfg = tmp_path / "active.json"
    xray_cfg.write_text(
        json.dumps(
            {
                "outbounds": [
                    {
                        "tag": "vless-1",
                        "protocol": "vless",
                        "settings": {"vnext": [{"address": "1.1.1.1"}]},
                    },
                    {
                        "tag": "vless-2",
                        "protocol": "vless",
                        "settings": {"vnext": [{"address": "2.2.2.2"}]},
                    },
                    {"tag": "direct", "protocol": "freedom"},
                ]
            }
        )
    )
    # No-op the atomic write so _rebuild_and_restart_xray doesn't stomp fixtures.
    monkeypatch.setattr("vless.manager._atomic_write_text", lambda p, c: None)
    return VlessProxyManager(
        pool_path=pool_path,
        cooldowns_path=cooldowns_path,
        events_path=events_path,
        xray_config_path=xray_cfg,
        register_atexit=False,
        log_func=lambda _: None,
    )


# ── _extract_running_hosts ────────────────────────────────────────────────

def test_extract_running_hosts_reads_active_json(pm):
    """Returns the union of all VLESS outbound vnext addresses."""
    hosts = pm._extract_running_hosts()
    assert hosts == {"1.1.1.1", "2.2.2.2"}


def test_extract_running_hosts_empty_on_missing_file(pm, tmp_path):
    """Missing config → empty set (recover-by-restart signal on first deploy)."""
    pm._xray_config_path = tmp_path / "does-not-exist.json"
    assert pm._extract_running_hosts() == set()


def test_extract_running_hosts_empty_on_malformed(pm):
    """Malformed JSON → empty set; do not raise."""
    pm._xray_config_path.write_text("{not json")
    assert pm._extract_running_hosts() == set()


# ── _reload_xray_systemd ──────────────────────────────────────────────────

def test_reload_skipped_on_windows(pm, monkeypatch):
    """Windows dev box → skip systemctl silently with clear marker."""
    monkeypatch.setattr(sys, "platform", "win32")
    outcome, dur, tail = pm._reload_xray_systemd()
    assert outcome == "skipped"
    assert tail == "platform=win32"
    assert dur is None


def test_reload_skipped_when_in_process_xray_owned(pm, monkeypatch):
    """Legacy test path owns its XrayProcess → systemctl path skipped."""
    monkeypatch.setattr(sys, "platform", "linux")

    class _FakeXray:
        def is_running(self):
            return True

    pm._xray = _FakeXray()  # type: ignore[assignment]
    outcome, dur, tail = pm._reload_xray_systemd()
    assert outcome == "skipped"
    assert tail == "in_process_xray_owned"
    assert dur is None


def test_reload_ok_updates_last_restart_monotonic(pm, monkeypatch):
    """Successful systemctl call records last_restart_monotonic and returns ok."""
    monkeypatch.setattr(sys, "platform", "linux")

    class _FakeCompleted:
        returncode = 0
        stderr = ""
        stdout = ""

    captured_argv: list[list[str]] = []

    def fake_run(argv, **_kwargs):
        captured_argv.append(list(argv))
        return _FakeCompleted()

    monkeypatch.setattr("subprocess.run", fake_run)
    outcome, dur, tail = pm._reload_xray_systemd()
    assert outcome == "ok"
    assert dur is not None and dur >= 0
    assert tail is None
    assert captured_argv == [SYSTEMCTL_ARGS]
    assert pm._last_xray_restart_monotonic > 0.0


def test_reload_throttled_within_window(pm, monkeypatch):
    """Second call within 90s returns 'throttled' without invoking subprocess."""
    monkeypatch.setattr(sys, "platform", "linux")
    # Simulate a recent successful restart.
    import time as _time

    pm._last_xray_restart_monotonic = _time.monotonic()

    called: list[bool] = []

    def fake_run(argv, **_kwargs):
        called.append(True)
        raise AssertionError("subprocess.run should not be called when throttled")

    monkeypatch.setattr("subprocess.run", fake_run)
    outcome, dur, tail = pm._reload_xray_systemd()
    assert outcome == "throttled"
    assert dur is None
    assert tail is None
    assert called == []


def test_reload_failed_on_nonzero_rc(pm, monkeypatch):
    """Non-zero rc → outcome='failed', stderr tail captured, timestamp NOT updated."""
    monkeypatch.setattr(sys, "platform", "linux")

    class _FakeCompleted:
        returncode = 1
        stderr = "Unit saleapp-xray.service not found."
        stdout = ""

    monkeypatch.setattr("subprocess.run", lambda argv, **kw: _FakeCompleted())
    before = pm._last_xray_restart_monotonic
    outcome, dur, tail = pm._reload_xray_systemd()
    assert outcome == "failed"
    assert dur is not None and dur >= 0
    assert tail == "Unit saleapp-xray.service not found."
    assert pm._last_xray_restart_monotonic == before  # NOT updated on failure


def test_reload_constants_locked():
    """Constants must match SPEC Lock in 68-CONTEXT.md (EC2 smoke 68-A)."""
    assert XRAY_RESTART_THROTTLE_S == 90.0
    assert XRAY_RESTART_TIMEOUT_S == 30.0
    assert SYSTEMCTL_ARGS == [
        "sudo",
        "systemctl",
        "reload-or-restart",
        "saleapp-xray",
    ]


# ── refresh_proxy_list wiring (68-02) ────────────────────────────────────

def _make_fake_node(host: str):
    """Return a VlessNode with only the fields _probe_candidates_in_parallel
    + replace_nodes need so the test doesn't pin unrelated parser internals."""
    from vless.parser import VlessNode

    return VlessNode(
        uuid="11111111-1111-1111-1111-111111111111",
        host=host,
        port=443,
        name="fake",
    )


def test_refresh_skips_reload_when_admitted_set_unchanged(pm, monkeypatch):
    """Admission set identical to running-config set → no systemctl call, outcome=unchanged."""
    # Seed active.json with the SAME host that admission will yield.
    pm._xray_config_path.write_text(
        json.dumps(
            {
                "outbounds": [
                    {
                        "tag": "vless-1",
                        "protocol": "vless",
                        "settings": {"vnext": [{"address": "7.7.7.7"}]},
                    }
                ]
            }
        )
    )
    fake = _make_fake_node("7.7.7.7")
    call_log: list[str] = []
    monkeypatch.setattr(
        pm,
        "_reload_xray_systemd",
        lambda: (call_log.append("called") or ("ok", 10, None)),
    )
    monkeypatch.setattr(
        "vless.manager.sources.fetch_igareck_list", lambda: "irrelevant"
    )
    monkeypatch.setattr(
        "vless.manager.sources.fetch_all_sources", lambda **_kw: "_fake_"
    )
    monkeypatch.setattr(
        "vless.manager.sources.parse_vless_list", lambda t: ([fake], [])
    )
    monkeypatch.setattr(
        "vless.manager.sources.filter_ru_nodes", lambda ns: ([fake], [])
    )
    monkeypatch.setattr(pm, "_probe_candidates_in_parallel", lambda cands: [fake])
    # _rebuild_and_restart_xray exercises the in-process path; stub it.
    monkeypatch.setattr(pm, "_rebuild_and_restart_xray", lambda: None)

    pm.refresh_proxy_list()

    # No reload call — set unchanged.
    assert call_log == []
    lines = [
        json.loads(line)
        for line in pm._events_path.read_text().splitlines()
        if line.strip()
    ]
    completes = [e for e in lines if e.get("event") == "pool_refresh_complete"]
    assert len(completes) == 1
    evt = completes[0]
    assert evt["restart_outcome"] == "unchanged"
    assert evt["xray_restart_triggered"] is False
    assert evt["added_hosts"] == []
    assert evt["removed_hosts"] == []


def test_refresh_triggers_reload_when_admitted_set_differs(pm, monkeypatch):
    """Admission set differs from running-config set → _reload_xray_systemd invoked,
    pool_refresh_complete event captures full diff."""
    # active.json already has 1.1.1.1 + 2.2.2.2 from the fixture.
    # Admission will yield 9.9.9.9 — diff forces reload.
    fake = _make_fake_node("9.9.9.9")
    call_log: list[str] = []

    def fake_reload():
        call_log.append("called")
        return "ok", 42, None

    monkeypatch.setattr(pm, "_reload_xray_systemd", fake_reload)
    monkeypatch.setattr(
        "vless.manager.sources.fetch_igareck_list", lambda: "irrelevant"
    )
    monkeypatch.setattr(
        "vless.manager.sources.fetch_all_sources", lambda **_kw: "_fake_"
    )
    monkeypatch.setattr(
        "vless.manager.sources.parse_vless_list", lambda t: ([fake], [])
    )
    monkeypatch.setattr(
        "vless.manager.sources.filter_ru_nodes", lambda ns: ([fake], [])
    )
    monkeypatch.setattr(pm, "_probe_candidates_in_parallel", lambda cands: [fake])
    monkeypatch.setattr(pm, "_rebuild_and_restart_xray", lambda: None)

    pm.refresh_proxy_list()

    assert call_log == ["called"]
    lines = [
        json.loads(line)
        for line in pm._events_path.read_text().splitlines()
        if line.strip()
    ]
    completes = [e for e in lines if e.get("event") == "pool_refresh_complete"]
    assert len(completes) == 1
    evt = completes[0]
    assert evt["restart_outcome"] == "ok"
    assert evt["xray_restart_triggered"] is True
    assert evt["admitted_hosts_after"] == ["9.9.9.9"]
    assert evt["admitted_hosts_before"] == ["1.1.1.1", "2.2.2.2"]
    assert evt["added_hosts"] == ["9.9.9.9"]
    assert evt["removed_hosts"] == ["1.1.1.1", "2.2.2.2"]
    assert evt["restart_duration_ms"] == 42


def test_refresh_emits_xray_restart_failed_event_on_systemctl_failure(pm, monkeypatch):
    """Non-ok reload outcome should emit a separate xray_restart_failed event."""
    fake = _make_fake_node("8.8.8.8")
    monkeypatch.setattr(
        pm,
        "_reload_xray_systemd",
        lambda: ("failed", 120, "Unit not found"),
    )
    monkeypatch.setattr(
        "vless.manager.sources.fetch_igareck_list", lambda: "irrelevant"
    )
    monkeypatch.setattr(
        "vless.manager.sources.fetch_all_sources", lambda **_kw: "_fake_"
    )
    monkeypatch.setattr(
        "vless.manager.sources.parse_vless_list", lambda t: ([fake], [])
    )
    monkeypatch.setattr(
        "vless.manager.sources.filter_ru_nodes", lambda ns: ([fake], [])
    )
    monkeypatch.setattr(pm, "_probe_candidates_in_parallel", lambda cands: [fake])
    monkeypatch.setattr(pm, "_rebuild_and_restart_xray", lambda: None)

    pm.refresh_proxy_list()

    lines = [
        json.loads(line)
        for line in pm._events_path.read_text().splitlines()
        if line.strip()
    ]
    failed_events = [e for e in lines if e.get("event") == "xray_restart_failed"]
    assert len(failed_events) == 1
    assert failed_events[0]["stderr_tail"] == "Unit not found"
    assert failed_events[0]["duration_ms"] == 120
    # pool_refresh_complete also emitted with outcome=failed
    completes = [e for e in lines if e.get("event") == "pool_refresh_complete"]
    assert len(completes) == 1
    assert completes[0]["restart_outcome"] == "failed"
    assert completes[0]["xray_restart_triggered"] is False


# ── pool_refresh_complete.success_rate_drops (69-02, OBS-07 completion) ───


def test_pool_refresh_complete_includes_success_rate_drops(pm, monkeypatch):
    """pool_refresh_complete carries hosts newly demoted to dead this cycle."""
    from vless.parser import VlessNode

    # Pre-seed the existing pool with one already-dead node and one
    # that will go dead during this refresh cycle.
    pm._pool["nodes"] = [
        {"host": "already-dead", "port": 443},
    ]
    # Record 20 failures for already-dead so it's graded dead NOW.
    for _ in range(20):
        pm.record_outcome("already-dead", success=False)
    # Record 20 failures for fresh-dead BEFORE refresh so it's graded
    # dead in the NEW pool as soon as admission lands it there.
    for _ in range(20):
        pm.record_outcome("fresh-dead", success=False)

    new_alive = VlessNode(uuid="u1", host="fresh-alive", port=443, name="alive")
    new_dead = VlessNode(uuid="u2", host="fresh-dead", port=443, name="dead")
    still_dead = VlessNode(
        uuid="u3", host="already-dead", port=443, name="stays-dead"
    )

    monkeypatch.setattr(pm, "_reload_xray_systemd", lambda: ("ok", 1, None))
    monkeypatch.setattr(
        "vless.manager.sources.fetch_igareck_list", lambda: "x"
    )
    monkeypatch.setattr(
        "vless.manager.sources.fetch_all_sources", lambda **_kw: "x"
    )
    monkeypatch.setattr(
        "vless.manager.sources.parse_vless_list",
        lambda t: ([new_alive, new_dead, still_dead], []),
    )
    monkeypatch.setattr(
        "vless.manager.sources.filter_ru_nodes",
        lambda ns: ([new_alive, new_dead, still_dead], []),
    )
    monkeypatch.setattr(
        pm, "_probe_candidates_in_parallel",
        lambda c: [new_alive, new_dead, still_dead],
    )
    monkeypatch.setattr(pm, "_rebuild_and_restart_xray", lambda: None)

    pm.refresh_proxy_list()

    lines = [
        json.loads(line)
        for line in pm._events_path.read_text().splitlines()
        if line.strip()
    ]
    completes = [e for e in lines if e.get("event") == "pool_refresh_complete"]
    assert len(completes) == 1
    evt = completes[0]
    assert "success_rate_drops" in evt
    # fresh-dead is newly dead in the new pool (20 failures recorded,
    # then admission places it in the pool — alive→dead in this cycle)
    assert "fresh-dead" in evt["success_rate_drops"]
    # already-dead was dead before AND after — not a drop
    assert "already-dead" not in evt["success_rate_drops"]
    # fresh-alive has no failure samples — not dead, not a drop
    assert "fresh-alive" not in evt["success_rate_drops"]

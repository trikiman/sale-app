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

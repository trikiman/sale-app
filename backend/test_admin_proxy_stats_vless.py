"""v1.26 regression: /admin/proxy-stats reads from the live VLESS pool
(vless_pool.json) not the dead v1.14 SOCKS5 cache (working_proxies.json).

Bug context: v1.15 migrated the proxy pool to VLESS+Reality but the admin
endpoint kept reading the frozen SOCKS5 cache. Operator saw 7 fake SOCKS5
entries with timestamps ~500-1130 hours old. This test pins the rewrite
so the endpoint can never silently drift back to reading the dead file.

Verification strategy:
1. Seed a fake vless_pool.json with two nodes (one dead by success_rate,
   one healthy).
2. Seed a working_proxies.json with *different* entries — if the endpoint
   still reads the legacy file, those entries would leak through.
3. Call /admin/proxy-stats, assert the response shape + fields come from
   the VLESS source and none of the legacy SOCKS5 entries appear.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


ADMIN_TOKEN_VALUE = "test-admin-token-proxy-stats"


@pytest.fixture
def configured_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """TestClient with admin token set + vless pool pointing to tmp path.

    Mirrors the pattern in test_admin_endpoints_v125.py — avoids
    importlib.reload(main) to keep route state intact across tests.
    """
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN_VALUE)

    # Seed a FAKE legacy SOCKS5 cache with bogus entries. If the endpoint
    # regresses to the old implementation these addresses will leak into
    # the response and the assertion at the bottom will catch it.
    legacy_cache = tmp_path / "working_proxies.json"
    legacy_cache.parent.mkdir(parents=True, exist_ok=True)
    legacy_cache.write_text(
        json.dumps(
            {
                "last_refresh": "2026-04-23T00:00:00",
                "proxies": [
                    {"addr": "DEAD_SOCKS5_ENTRY:1080", "speed": 99.0, "alive": True},
                ],
            }
        )
    )

    # Seed a live VLESS pool that the rewritten endpoint MUST read.
    vless_pool = tmp_path / "vless_pool.json"
    vless_pool.write_text(
        json.dumps(
            {
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "nodes": [
                    {
                        "uuid": "aaaa",
                        "host": "1.2.3.4",
                        "port": 443,
                        "name": "RU-moscow-test",
                        "reality_pbk": "pbk",
                        "reality_sni": "sni",
                        "reality_sid": "",
                        "reality_spx": "",
                        "reality_fp": "chrome",
                        "flow": "",
                        "transport": "tcp",
                        "encryption": "none",
                        "header_type": "none",
                        "security": "reality",
                        "tls_sni": "",
                        "tls_allow_insecure": False,
                        "verified_country": "RU",
                        "verified_at": datetime.now().isoformat(timespec="seconds"),
                        "last_success_at": None,
                        "success_count": 0,
                        "failure_count": 0,
                        "extra": {"probe_speed_s": 1.23},
                    },
                    {
                        "uuid": "bbbb",
                        "host": "5.6.7.8",
                        "port": 443,
                        "name": "RU-spb-slow",
                        "reality_pbk": "pbk2",
                        "reality_sni": "sni2",
                        "reality_sid": "",
                        "reality_spx": "",
                        "reality_fp": "chrome",
                        "flow": "",
                        "transport": "tcp",
                        "encryption": "none",
                        "header_type": "none",
                        "security": "reality",
                        "tls_sni": "",
                        "tls_allow_insecure": False,
                        "verified_country": "RU",
                        "verified_at": datetime.now().isoformat(timespec="seconds"),
                        "last_success_at": None,
                        "success_count": 0,
                        "failure_count": 0,
                        "extra": {"probe_speed_s": 4.56},
                    },
                ],
            }
        )
    )

    # Redirect pool_state + manager to the tmp pool.
    from vless import pool_state as _pool_state
    monkeypatch.setattr(_pool_state, "POOL_PATH_DEFAULT", vless_pool)

    import backend.main as main
    monkeypatch.setattr(main, "ADMIN_TOKEN", ADMIN_TOKEN_VALUE)

    # Swap the running manager's view of the pool.
    # pool_snapshot() reads from self._pool (in-memory), so we also prime
    # that by loading the fresh file.
    main._proxy_manager._pool = _pool_state.load(vless_pool)

    return TestClient(main.app), main


def test_proxy_stats_reads_from_vless_pool_not_legacy_cache(configured_client):
    client, _main = configured_client
    resp = client.get(
        "/admin/proxy-stats",
        headers={"X-Admin-Token": ADMIN_TOKEN_VALUE},
    )
    assert resp.status_code == 200
    data = resp.json()

    # Shape contract expected by admin.html + backwards compat.
    assert "pool_size" in data
    assert "min_healthy" in data
    assert "healthy" in data
    assert "cache_age_min" in data
    assert "proxies" in data
    assert isinstance(data["proxies"], list)

    # v1.26 source marker — rules out a regression to the SOCKS5 cache.
    assert data.get("pool_source") == "vless"

    # Must reflect the 2 VLESS nodes, not the 1 legacy SOCKS5 entry.
    assert data["pool_size"] == 2, f"expected 2, got {data['pool_size']}"
    assert len(data["proxies"]) == 2

    # Entries must be the VLESS hosts, not the dead SOCKS5 stub.
    addresses = [p["addr"] for p in data["proxies"]]
    assert "DEAD_SOCKS5_ENTRY:1080" not in addresses, (
        "regression: endpoint leaked the legacy SOCKS5 cache"
    )
    assert "1.2.3.4:443" in addresses
    assert "5.6.7.8:443" in addresses

    # Protocol label must be vless (admin.html colours it differently).
    for proxy in data["proxies"]:
        assert proxy["protocol"] == "vless"
        assert proxy["country"] == "RU"

    # Speed pulled from extra.probe_speed_s; row order sorts by it.
    assert data["proxies"][0]["speed"] == 1.23
    assert data["proxies"][1]["speed"] == 4.56


def test_proxy_stats_requires_admin_token(configured_client):
    client, _main = configured_client
    resp = client.get("/admin/proxy-stats")
    assert resp.status_code in (401, 403)

    resp = client.get(
        "/admin/proxy-stats",
        headers={"X-Admin-Token": "wrong-token"},
    )
    assert resp.status_code in (401, 403)


def test_proxy_stats_returns_empty_list_when_pool_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Pool file doesn't exist yet (fresh deploy) -> graceful empty list,
    not a 500. pool_state.load() returns ``{"updated_at": None,
    "nodes": []}`` per its FileNotFoundError branch."""
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN_VALUE)
    from vless import pool_state as _pool_state
    monkeypatch.setattr(_pool_state, "POOL_PATH_DEFAULT", tmp_path / "missing.json")

    import backend.main as main
    monkeypatch.setattr(main, "ADMIN_TOKEN", ADMIN_TOKEN_VALUE)
    main._proxy_manager._pool = {"updated_at": None, "nodes": []}

    client = TestClient(main.app)
    resp = client.get(
        "/admin/proxy-stats",
        headers={"X-Admin-Token": ADMIN_TOKEN_VALUE},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["pool_size"] == 0
    assert data["proxies"] == []
    assert data["healthy"] is False


# v1.26 Phase 84.1 — /admin/vless/quarantine read-only snapshot endpoint.

def test_quarantine_get_groups_entries_by_tier(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """v1.26 Phase 84.1: GET /admin/vless/quarantine groups entries into
    soft / hard / repeat_offender tiers and reports per-reason counts.
    Pins the operator-visibility contract used by the admin panel.
    """
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN_VALUE)
    monkeypatch.setenv("SALEAPP_POOL_QUARANTINE_PATH", str(tmp_path / "q.json"))

    import importlib
    from vless import quarantine
    importlib.reload(quarantine)

    import time as _t
    monkeypatch.setattr(_t, "time", lambda: 1000.0)
    # Soft tier (60s, transient)
    quarantine.record_probe_failure("soft.host:443", reason="probe_timeout")
    # Hard tier (20m, vpn_detected)
    quarantine.record_probe_failure("blocked.exit:443", reason="vpn_detected")
    # Repeat offender (4h, after 3 strikes)
    for ts in (1000.0, 1010.0, 1020.0):
        monkeypatch.setattr(_t, "time", lambda ts=ts: ts)
        quarantine.record_probe_failure("dead.host:443", reason="probe_error")

    import backend.main as main
    monkeypatch.setattr(main, "ADMIN_TOKEN", ADMIN_TOKEN_VALUE)
    client = TestClient(main.app)

    resp = client.get(
        "/admin/vless/quarantine",
        headers={"X-Admin-Token": ADMIN_TOKEN_VALUE},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["count"] == 3
    assert data["by_tier"]["soft"] == 1
    assert data["by_tier"]["hard"] == 1
    assert data["by_tier"]["repeat_offender"] == 1
    assert data["by_reason"]["probe_timeout"] == 1
    assert data["by_reason"]["vpn_detected"] == 1
    assert data["by_reason"]["probe_error"] == 1

    entry_keys = {e["host_port"] for e in data["entries"]}
    assert entry_keys == {"soft.host:443", "blocked.exit:443", "dead.host:443"}
    # Soft entry sorts first because it expires soonest.
    assert data["entries"][0]["host_port"] == "soft.host:443"
    assert data["entries"][0]["tier"] == "soft"


def test_quarantine_get_requires_admin_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN_VALUE)
    import backend.main as main
    monkeypatch.setattr(main, "ADMIN_TOKEN", ADMIN_TOKEN_VALUE)
    client = TestClient(main.app)
    resp = client.get("/admin/vless/quarantine")
    assert resp.status_code in (401, 403)

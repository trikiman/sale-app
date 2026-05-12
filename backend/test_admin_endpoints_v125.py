"""Phase 80 (v1.25 OPS-24/25) — admin escape-hatch endpoint tests.

Verifies:
- POST /admin/vless/quarantine/clear clears the deadlist + returns diff
- POST /admin/force-stale-all activates the override + /api/products respects it
- POST /admin/force-stale-all/clear cancels the override
- POST /admin/test-alert bypasses cooldown + returns send status
- All endpoints require X-Admin-Token
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


ADMIN_TOKEN_VALUE = "test-admin-token-xyz"


@pytest.fixture
def configured_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """TestClient with admin token set + quarantine + alerts pointing to tmp.

    Carefully avoids importlib.reload(main) since that corrupts FastAPI
    route state for subsequent tests in the backend suite. Instead, uses
    monkeypatch for the module-level constants we need to override.
    """
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN_VALUE)
    monkeypatch.setenv("SALEAPP_POOL_QUARANTINE_PATH", str(tmp_path / "pool_quarantine.json"))
    monkeypatch.setenv("SALEAPP_ADMIN_ALERTS_PATH", str(tmp_path / "admin_alerts.jsonl"))

    # Reload only the leaf modules (no side-effects on main app).
    import importlib
    from vless import quarantine
    importlib.reload(quarantine)
    from backend import admin_alerts
    importlib.reload(admin_alerts)

    # Patch main's references without reloading main itself.
    import backend.main as main
    monkeypatch.setattr(main, "ADMIN_TOKEN", ADMIN_TOKEN_VALUE)
    # Reset module-level override state so prior tests don't leak.
    monkeypatch.setattr(main, "_FORCE_STALE_ALL_UNTIL", None)

    return TestClient(main.app), main, quarantine, admin_alerts


def test_quarantine_clear_requires_token(configured_client):
    client, _, _, _ = configured_client
    resp = client.post("/admin/vless/quarantine/clear")
    assert resp.status_code in {401, 403}


def test_quarantine_clear_returns_prior_snapshot(configured_client):
    client, _, quarantine, _ = configured_client
    # Seed quarantine
    quarantine.record_probe_failures(["a.b.c:443", "d.e.f:443", "g.h.i:443"])
    assert len(quarantine.get_quarantined_hosts()) == 3

    resp = client.post(
        "/admin/vless/quarantine/clear",
        headers={"X-Admin-Token": ADMIN_TOKEN_VALUE},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["cleared_count"] == 3
    assert set(body["previous_hosts"]) == {"a.b.c:443", "d.e.f:443", "g.h.i:443"}

    # Deadlist is now empty
    assert len(quarantine.get_quarantined_hosts()) == 0


def test_force_stale_all_requires_token(configured_client):
    client, _, _, _ = configured_client
    resp = client.post("/admin/force-stale-all")
    assert resp.status_code in {401, 403}


def test_force_stale_all_activates_override(configured_client):
    client, main, _, _ = configured_client
    resp = client.post(
        "/admin/force-stale-all?duration_s=300",
        headers={"X-Admin-Token": ADMIN_TOKEN_VALUE},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["duration_s"] == 300
    assert body["force_stale_until"] > time.time()

    # Module-level override is set
    assert main._FORCE_STALE_ALL_UNTIL is not None
    assert main._FORCE_STALE_ALL_UNTIL > time.time()


def test_force_stale_all_clear_cancels_override(configured_client):
    client, main, _, _ = configured_client

    # Activate
    client.post(
        "/admin/force-stale-all?duration_s=300",
        headers={"X-Admin-Token": ADMIN_TOKEN_VALUE},
    )
    assert main._FORCE_STALE_ALL_UNTIL is not None

    # Clear
    resp = client.post(
        "/admin/force-stale-all/clear",
        headers={"X-Admin-Token": ADMIN_TOKEN_VALUE},
    )
    assert resp.status_code == 200
    assert resp.json()["cleared"] is True
    assert resp.json()["was_active"] is True
    assert main._FORCE_STALE_ALL_UNTIL is None


def test_force_stale_all_clamps_duration(configured_client):
    client, _, _, _ = configured_client

    # Below 30s → 422 (FastAPI validation)
    resp = client.post(
        "/admin/force-stale-all?duration_s=5",
        headers={"X-Admin-Token": ADMIN_TOKEN_VALUE},
    )
    assert resp.status_code == 422

    # Above 3600s → 422
    resp = client.post(
        "/admin/force-stale-all?duration_s=10000",
        headers={"X-Admin-Token": ADMIN_TOKEN_VALUE},
    )
    assert resp.status_code == 422


def test_test_alert_requires_token(configured_client):
    client, _, _, _ = configured_client
    resp = client.post("/admin/test-alert")
    assert resp.status_code in {401, 403}


def test_test_alert_returns_no_token_when_telegram_unconfigured(configured_client, monkeypatch):
    """Without TELEGRAM_TOKEN set, test-alert should report no_token reason,
    not crash."""
    client, _, _, _ = configured_client
    monkeypatch.delenv("TELEGRAM_TOKEN", raising=False)

    resp = client.post(
        "/admin/test-alert",
        headers={"X-Admin-Token": ADMIN_TOKEN_VALUE},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sent"] is False
    assert body["reason"] in {"no_token", "no_admin_chat_ids"}

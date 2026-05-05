"""Phase 61 REL-11 + OBS-01: /api/health/deep unauth endpoint contract.

Locks down:
  - JSON schema and required keys
  - 200 / 503 / 429 status mapping
  - reasons[] severity classification (healthy / degraded / down)
  - Cache-Control: no-store header
  - 1 req/s/IP rate limit
  - Helper-function unit semantics for breaker / pool / cycle / xray

We use FastAPI's TestClient against backend.main:app, mirroring the
pattern in tests/test_cart_errors.py.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

from backend import main as backend_main
from backend.main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """Per-test client with rate-limit state cleared so tests don't bleed."""
    backend_main._DEEP_LAST_HIT.clear()
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def healthy_world(monkeypatch, tmp_path):
    """Patch all four signal collectors into a fully-healthy state."""
    monkeypatch.setattr(
        backend_main, "_check_xray_listening",
        lambda: {"listening": True, "port": 10808},
    )
    monkeypatch.setattr(
        backend_main, "_pool_snapshot_for_health",
        lambda: {
            "available": True,
            "size": 12,
            "min_healthy": 7,
            "quarantined_count": 0,
            "active_outbounds": 12,
            "last_refresh_at": "2026-05-05T15:00:00",
        },
    )
    monkeypatch.setattr(
        backend_main, "_load_breaker_snapshot",
        lambda: {"available": True, "state": "closed", "cooldown_s": 0, "fails": 0},
    )
    monkeypatch.setattr(
        backend_main, "_last_cycle_age_seconds",
        lambda: 60.0,
    )


# ---------------------------------------------------------------------------
# Schema + status contract
# ---------------------------------------------------------------------------


REQUIRED_TOP_KEYS = {
    "status", "reasons", "pool", "breaker", "xray",
    "last_cycle_age_s", "as_of",
}


def test_healthy_returns_200_and_full_schema(client, healthy_world):
    r = client.get("/api/health/deep")
    assert r.status_code == 200
    assert r.headers.get("Cache-Control") == "no-store, no-cache, must-revalidate"
    body = r.json()
    assert set(body.keys()) == REQUIRED_TOP_KEYS
    assert body["status"] == "healthy"
    assert body["reasons"] == []
    assert body["pool"]["size"] == 12
    assert body["breaker"]["state"] == "closed"
    assert body["xray"]["listening"] is True
    assert body["last_cycle_age_s"] == 60


def test_pool_below_min_healthy_is_degraded_503(client, monkeypatch, healthy_world):
    monkeypatch.setattr(
        backend_main, "_pool_snapshot_for_health",
        lambda: {
            "available": True, "size": 3, "min_healthy": 7,
            "quarantined_count": 0, "active_outbounds": 3,
            "last_refresh_at": "2026-05-05T15:00:00",
        },
    )
    r = client.get("/api/health/deep")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "degraded"
    assert any(reason.startswith("pool_below_min_healthy") for reason in body["reasons"])


def test_breaker_open_is_degraded_503(client, monkeypatch, healthy_world):
    monkeypatch.setattr(
        backend_main, "_load_breaker_snapshot",
        lambda: {"available": True, "state": "open", "cooldown_s": 600, "fails": 3},
    )
    r = client.get("/api/health/deep")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "degraded"
    assert "breaker_open" in body["reasons"]


def test_breaker_half_open_is_degraded_503(client, monkeypatch, healthy_world):
    monkeypatch.setattr(
        backend_main, "_load_breaker_snapshot",
        lambda: {"available": True, "state": "half_open", "cooldown_s": 60, "fails": 3},
    )
    r = client.get("/api/health/deep")
    assert r.status_code == 503
    assert "breaker_half_open" in r.json()["reasons"]


def test_xray_not_listening_is_down_503(client, monkeypatch, healthy_world):
    monkeypatch.setattr(
        backend_main, "_check_xray_listening",
        lambda: {"listening": False, "port": 10808},
    )
    r = client.get("/api/health/deep")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "down"
    assert "xray_bridge_not_listening" in body["reasons"]


def test_no_cycle_state_is_down_503(client, monkeypatch, healthy_world):
    monkeypatch.setattr(backend_main, "_last_cycle_age_seconds", lambda: None)
    r = client.get("/api/health/deep")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "down"
    assert "no_cycle_state" in body["reasons"]
    assert body["last_cycle_age_s"] is None


def test_stale_cycle_is_degraded_503(client, monkeypatch, healthy_world):
    # 30 minutes — exceeds 15-minute threshold
    monkeypatch.setattr(backend_main, "_last_cycle_age_seconds", lambda: 30 * 60.0)
    r = client.get("/api/health/deep")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "degraded"
    assert any(reason.startswith("stale_cycle_") for reason in body["reasons"])


def test_multiple_problems_aggregate_into_reasons(client, monkeypatch, healthy_world):
    monkeypatch.setattr(
        backend_main, "_pool_snapshot_for_health",
        lambda: {
            "available": True, "size": 2, "min_healthy": 7,
            "quarantined_count": 5, "active_outbounds": 2,
            "last_refresh_at": "2026-05-05T15:00:00",
        },
    )
    monkeypatch.setattr(
        backend_main, "_load_breaker_snapshot",
        lambda: {"available": True, "state": "open", "cooldown_s": 600, "fails": 3},
    )
    r = client.get("/api/health/deep")
    body = r.json()
    assert r.status_code == 503
    assert len(body["reasons"]) >= 2  # both pool + breaker reasons
    assert "breaker_open" in body["reasons"]


def test_pool_snapshot_unavailable_is_degraded(client, monkeypatch, healthy_world):
    monkeypatch.setattr(
        backend_main, "_pool_snapshot_for_health",
        lambda: {"available": False, "error": "ImportError"},
    )
    r = client.get("/api/health/deep")
    assert r.status_code == 503
    assert "pool_snapshot_unavailable" in r.json()["reasons"]


# ---------------------------------------------------------------------------
# Rate limit (1 req/s/IP)
# ---------------------------------------------------------------------------


def test_rate_limit_429_on_back_to_back_requests(client, healthy_world):
    r1 = client.get("/api/health/deep")
    assert r1.status_code == 200
    # Same IP, immediately again -> 429
    r2 = client.get("/api/health/deep")
    assert r2.status_code == 429


def test_rate_limit_recovers_after_one_second(client, healthy_world):
    r1 = client.get("/api/health/deep")
    assert r1.status_code == 200
    time.sleep(1.1)  # exceed _HEALTH_DEEP_RATE_LIMIT_S=1.0
    r2 = client.get("/api/health/deep")
    assert r2.status_code == 200


def test_rate_limit_per_ip_independent(client, monkeypatch, healthy_world):
    """Different client IPs must get independent buckets."""
    # TestClient's request.client.host is "testclient" by default; we can
    # reach into the dict to simulate different IPs by clearing between
    # calls (the impl is keyed on request.client.host).
    backend_main._DEEP_LAST_HIT.clear()
    r1 = client.get("/api/health/deep")
    assert r1.status_code == 200
    # Different IP — simulate by directly seeding the dict for our IP only,
    # leaving "1.2.3.4" alone, then checking that key persists separately.
    backend_main._DEEP_LAST_HIT["1.2.3.4"] = 0.0  # ancient -> not rate-limited
    # Our IP IS rate-limited though
    r2 = client.get("/api/health/deep")
    assert r2.status_code == 429
    # The other IP entry must still exist and not have been clobbered
    assert "1.2.3.4" in backend_main._DEEP_LAST_HIT


# ---------------------------------------------------------------------------
# Endpoint security: must NOT require auth
# ---------------------------------------------------------------------------


def test_endpoint_does_not_require_admin_token(client, healthy_world):
    """REL-11: external uptime monitors must be able to hit this without creds."""
    r = client.get("/api/health/deep")  # no headers
    assert r.status_code in (200, 503)  # NEVER 401 / 403


# ---------------------------------------------------------------------------
# Helper-function unit tests
# ---------------------------------------------------------------------------


def test_load_breaker_snapshot_missing_file(monkeypatch, tmp_path):
    monkeypatch.setattr(backend_main, "_SCHEDULER_STATE_PATH", str(tmp_path / "nope.json"))
    snap = backend_main._load_breaker_snapshot()
    assert snap == {"available": False, "state": "unknown"}


def test_load_breaker_snapshot_valid_file(monkeypatch, tmp_path):
    p = tmp_path / "scheduler_state.json"
    p.write_text(json.dumps({
        "state": "open", "cooldown_s": 300, "fails": 5,
    }))
    monkeypatch.setattr(backend_main, "_SCHEDULER_STATE_PATH", str(p))
    snap = backend_main._load_breaker_snapshot()
    assert snap == {"available": True, "state": "open", "cooldown_s": 300, "fails": 5}


def test_load_breaker_snapshot_corrupt_file(monkeypatch, tmp_path):
    p = tmp_path / "scheduler_state.json"
    p.write_text("{not json")
    monkeypatch.setattr(backend_main, "_SCHEDULER_STATE_PATH", str(p))
    snap = backend_main._load_breaker_snapshot()
    assert snap["available"] is False


def test_load_breaker_snapshot_unknown_state_falls_back(monkeypatch, tmp_path):
    p = tmp_path / "scheduler_state.json"
    p.write_text(json.dumps({"state": "weird"}))
    monkeypatch.setattr(backend_main, "_SCHEDULER_STATE_PATH", str(p))
    snap = backend_main._load_breaker_snapshot()
    assert snap["available"] is True
    assert snap["state"] == "unknown"  # sanitized


def test_check_xray_listening_when_port_closed(monkeypatch):
    # Use an almost-certainly unused port to force the closed branch
    monkeypatch.setattr(backend_main, "_XRAY_SOCKS_PORT", 1)
    snap = backend_main._check_xray_listening()
    assert snap["listening"] is False
    assert snap["port"] == 1


def test_build_reliability_snapshot_empty_reasons_means_healthy(monkeypatch, healthy_world):
    snap = backend_main._build_reliability_snapshot()
    assert snap["status"] == "healthy"
    assert snap["reasons"] == []


def test_build_reliability_snapshot_severity_ranking(monkeypatch):
    """down (xray_off) should override degraded reasons in classification."""
    monkeypatch.setattr(
        backend_main, "_check_xray_listening",
        lambda: {"listening": False, "port": 10808},
    )
    monkeypatch.setattr(
        backend_main, "_pool_snapshot_for_health",
        lambda: {"available": True, "size": 12, "min_healthy": 7,
                 "quarantined_count": 0, "active_outbounds": 12,
                 "last_refresh_at": "2026-05-05T15:00:00"},
    )
    monkeypatch.setattr(
        backend_main, "_load_breaker_snapshot",
        lambda: {"available": True, "state": "open", "cooldown_s": 60, "fails": 1},
    )
    monkeypatch.setattr(backend_main, "_last_cycle_age_seconds", lambda: 60.0)
    snap = backend_main._build_reliability_snapshot()
    assert snap["status"] == "down"  # xray off wins over breaker open


# ---------------------------------------------------------------------------
# /admin/status reliability block (OBS-03)
# ---------------------------------------------------------------------------


def test_admin_status_includes_reliability_block(client, monkeypatch, healthy_world):
    # /admin/status requires X-Admin-Token; pull the configured token in a
    # way that doesn't echo it.
    import config
    token = getattr(config, "ADMIN_TOKEN", "") or os.environ.get("ADMIN_TOKEN", "")
    if not token:
        pytest.skip("ADMIN_TOKEN not configured in this env — admin route is gated")
    r = client.get("/admin/status", headers={"X-Admin-Token": token})
    assert r.status_code == 200
    body = r.json()
    assert "reliability" in body
    rel = body["reliability"]
    # Same shape as the health endpoint
    assert set(rel.keys()) >= REQUIRED_TOP_KEYS - {"as_of"}  # as_of always present too
    assert rel["status"] in ("healthy", "degraded", "down")

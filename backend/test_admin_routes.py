import pytest
from fastapi.testclient import TestClient
import os
import tempfile
import json
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backend.main as main


client = TestClient(main.app)


class DummyThread:
    def __init__(self, target=None, daemon=None):
        self.target = target
        self.daemon = daemon

    def start(self):
        # Prevent the real scraper subprocess from starting during route tests.
        return None


@pytest.fixture(autouse=True)
def reset_categories_status():
    previous = dict(main.scraper_status["categories"])
    main.scraper_status["categories"] = {
        "running": False,
        "last_run": None,
        "exit_code": None,
        "last_output": "",
    }
    try:
        yield
    finally:
        main.scraper_status["categories"] = previous


def test_categories_route_is_public_and_not_captured_by_tokenized_scraper_route(monkeypatch):
    monkeypatch.setattr(main.threading, "Thread", DummyThread)

    response = client.post("/api/admin/run/categories")

    assert response.status_code == 200
    assert response.json()["started"] == "categories"


def test_failed_scraper_does_not_auto_merge(monkeypatch):
    calls = []

    def fake_run_script(name, script_path):
        calls.append(name)
        main.scraper_status[name]["running"] = False
        main.scraper_status[name]["exit_code"] = 1 if name == "green" else 0

    monkeypatch.setattr(main, "_run_script", fake_run_script)
    monkeypatch.setattr(main._time, "sleep", lambda _seconds: None)

    response = client.post(
        "/api/admin/run/green",
        headers={"X-Admin-Token": main.ADMIN_TOKEN},
    )

    assert response.status_code == 200
    assert calls == ["green"]


def test_copy_tech_profile_replaces_previous_profile():
    with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as dst_parent:
        src_marker = os.path.join(src_dir, "Profile Marker.txt")
        with open(src_marker, "w", encoding="utf-8") as f:
            f.write("fresh-profile")

        dst_dir = os.path.join(dst_parent, "tech_profile")
        os.makedirs(dst_dir, exist_ok=True)
        with open(os.path.join(dst_dir, "stale.txt"), "w", encoding="utf-8") as f:
            f.write("stale")

        main._copy_tech_profile(src_dir, dst_dir)

        assert os.path.exists(os.path.join(dst_dir, "Profile Marker.txt"))
        assert not os.path.exists(os.path.join(dst_dir, "stale.txt"))


def test_admin_status_includes_cycle_state(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    cycle_state_path = data_dir / "scrape_cycle_state.json"
    cycle_state_path.write_text(
        json.dumps(
            {
                "continuity_safe": False,
                "overall_status": "degraded",
                "reasons": ["green:timeout"],
                "sources": {
                    "green": {"status": "timeout", "status_text": "TIMEOUT", "counted_for_continuity": False},
                    "red": {"status": "ok", "status_text": "OK", "counted_for_continuity": True},
                    "yellow": {"status": "ok", "status_text": "OK", "counted_for_continuity": True},
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(main, "DATA_DIR", str(data_dir))

    response = client.get("/admin/status", headers={"X-Admin-Token": main.ADMIN_TOKEN})

    assert response.status_code == 200
    body = response.json()
    assert body["cycleState"]["continuity_safe"] is False
    assert body["cycleState"]["sources"]["green"]["status"] == "timeout"
    assert set(body["sourceFreshness"].keys()) == {"green", "red", "yellow"}


def test_admin_status_includes_cart_diagnostics(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(main, "DATA_DIR", str(data_dir))

    main._cart_add_attempts.clear()
    main._cart_add_attempt_index.clear()
    main._cart_add_attempts["attempt-1"] = {
        "attempt_id": "attempt-1",
        "user_id": "123",
        "product_id": 500,
        "status": "success",
        "final_status": "success",
        "created_at": 1.0,
        "started_at": 1.0,
        "resolved_at": 2.0,
        "duration_ms": 1000,
        "expires_at": 9999999999.0,
        "source": "status_lookup_cart",
        "last_error": None,
        "cart_items": 2,
        "cart_total": 182,
    }

    response = client.get("/admin/status", headers={"X-Admin-Token": main.ADMIN_TOKEN})

    assert response.status_code == 200
    body = response.json()
    assert "cartDiagnostics" in body
    assert body["cartDiagnostics"]["pendingCount"] == 0
    assert body["cartDiagnostics"]["lastResolvedAt"] == 2.0
    assert body["cartDiagnostics"]["recentAttempts"][0]["attempt_id"] == "attempt-1"
    assert body["cartDiagnostics"]["recentAttempts"][0]["duration_ms"] == 1000

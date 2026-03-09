import pytest
from fastapi.testclient import TestClient
import os
import tempfile

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

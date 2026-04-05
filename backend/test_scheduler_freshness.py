import json
from pathlib import Path
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

import backend.main as main
import scheduler_service


client = TestClient(main.app)


def test_choose_due_job_runs_full_cycle_when_due():
    assert scheduler_service.choose_due_job(300.0, 300.0, 240.0, 60.0) == "all"


def test_choose_due_job_runs_green_when_green_due_and_full_not_at_risk():
    assert scheduler_service.choose_due_job(120.0, 300.0, 120.0, 60.0) == "green"


def test_choose_due_job_skips_green_when_full_cycle_would_be_late():
    assert scheduler_service.choose_due_job(250.0, 300.0, 240.0, 60.0) == "skip_green"


def test_products_route_exposes_source_freshness(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    proposals_path = data_dir / "proposals.json"
    proposals_path.write_text(json.dumps({"updatedAt": "2026-04-05 12:00:00", "products": []}), encoding="utf-8")

    for color in ("green", "red", "yellow"):
        (data_dir / f"{color}_products.json").write_text(json.dumps({"products": []}), encoding="utf-8")

    monkeypatch.setattr(main, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(main, "PROPOSALS_PATH", str(proposals_path))

    response = client.get("/api/products")
    assert response.status_code == 200
    body = response.json()
    assert set(body["sourceFreshness"].keys()) == {"green", "red", "yellow"}
    assert "cycleState" in body

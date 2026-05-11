"""v1.20 Phase 66.1 — Stale-Color Phantom Strip unit tests.

Pins the behavior that when a color's source file is flagged
isStale=True by _build_source_freshness, products of that `type` are
dropped from /api/products response while the banner-driving fields
(dataStale, staleInfo, sourceFreshness) keep their original values.

Mirrors backend/test_scheduler_freshness.py fixture conventions:
monkeypatch DATA_DIR + PROPOSALS_PATH to tmp_path, write synthetic
proposals.json + per-color files, monkeypatch _build_source_freshness
for determinism.
"""
import json
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backend.main as main  # noqa: E402


def _synthetic_proposals():
    return {
        "updatedAt": "2026-05-12 12:00:00",
        "products": [
            {
                "id": "g1", "name": "Green Apple", "url": "https://vkusvill.ru/g1",
                "currentPrice": "10", "oldPrice": "20", "image": "", "stock": 1,
                "unit": "шт", "category": "Fruit", "type": "green",
            },
            {
                "id": "g2", "name": "Green Banana", "url": "https://vkusvill.ru/g2",
                "currentPrice": "15", "oldPrice": "25", "image": "", "stock": 1,
                "unit": "шт", "category": "Fruit", "type": "green",
            },
            {
                "id": "r1", "name": "Red Apple", "url": "https://vkusvill.ru/r1",
                "currentPrice": "12", "oldPrice": "22", "image": "", "stock": 1,
                "unit": "шт", "category": "Fruit", "type": "red",
            },
            {
                "id": "y1", "name": "Yellow Pear", "url": "https://vkusvill.ru/y1",
                "currentPrice": "18", "oldPrice": "28", "image": "", "stock": 1,
                "unit": "шт", "category": "Fruit", "type": "yellow",
            },
        ],
    }


def _seed_data_dir(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    proposals_path = data_dir / "proposals.json"
    proposals_path.write_text(
        json.dumps(_synthetic_proposals(), ensure_ascii=False),
        encoding="utf-8",
    )
    # Each color file present + non-empty so greenMissing=False.
    for color in ("green", "red", "yellow"):
        (data_dir / f"{color}_products.json").write_text(
            json.dumps({"products": [{"id": f"{color}-seed"}]}),
            encoding="utf-8",
        )
    monkeypatch.setattr(main, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(main, "PROPOSALS_PATH", str(proposals_path))
    return data_dir


def _patch_freshness(monkeypatch, *, green_stale, red_stale, yellow_stale):
    """Monkeypatch _build_source_freshness to return deterministic state."""
    stale_files = []
    source_freshness = {}
    for color, is_stale in (
        ("green", green_stale),
        ("red", red_stale),
        ("yellow", yellow_stale),
    ):
        age_min = 30.0 if is_stale else 3.0
        source_freshness[color] = {
            "exists": True,
            "updatedAt": "2026-05-12T12:00:00",
            "ageMinutes": age_min,
            "isStale": is_stale,
            "status": "stale" if is_stale else "ok",
        }
        if is_stale:
            stale_files.append(f"{color} ({age_min:.0f}m)")
    latest_mtime = 1_778_000_000.0

    def _fake(stale_minutes: int = 10):
        return source_freshness, stale_files, latest_mtime

    monkeypatch.setattr(main, "_build_source_freshness", _fake)


def test_stale_green_drops_green_products(monkeypatch, tmp_path):
    """Green source stale, red+yellow fresh -> 2 green products dropped,
    1 red + 1 yellow survive, banner fields intact."""
    _seed_data_dir(tmp_path, monkeypatch)
    _patch_freshness(monkeypatch, green_stale=True, red_stale=False, yellow_stale=False)

    client = TestClient(main.app)
    resp = client.get("/api/products")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Phantom green cards must be gone.
    types = [p.get("type") for p in body["products"]]
    assert "green" not in types, f"green survived the filter: {types}"
    assert types.count("red") == 1
    assert types.count("yellow") == 1
    assert len(body["products"]) == 2

    # Banner fields must survive untouched.
    assert body["dataStale"] is True
    assert body["sourceFreshness"]["green"]["isStale"] is True
    assert body["sourceFreshness"]["red"]["isStale"] is False
    assert body["sourceFreshness"]["yellow"]["isStale"] is False
    assert body["staleInfo"] == ["green (30m)"]


def test_all_stale_drops_everything(monkeypatch, tmp_path):
    """All three colors stale -> empty products list; banner fields still
    carry all three stale entries."""
    _seed_data_dir(tmp_path, monkeypatch)
    _patch_freshness(monkeypatch, green_stale=True, red_stale=True, yellow_stale=True)

    client = TestClient(main.app)
    resp = client.get("/api/products")
    assert resp.status_code == 200
    body = resp.json()

    assert body["products"] == []
    assert body["dataStale"] is True
    assert len(body["staleInfo"]) == 3
    for color in ("green", "red", "yellow"):
        assert body["sourceFreshness"][color]["isStale"] is True


def test_none_stale_no_regression(monkeypatch, tmp_path):
    """No sources stale -> all 4 synthetic products present, dataStale False.
    Proves the filter is a no-op when not needed (no regression)."""
    _seed_data_dir(tmp_path, monkeypatch)
    _patch_freshness(monkeypatch, green_stale=False, red_stale=False, yellow_stale=False)

    client = TestClient(main.app)
    resp = client.get("/api/products")
    assert resp.status_code == 200
    body = resp.json()

    types = sorted(p.get("type") for p in body["products"])
    assert types == ["green", "green", "red", "yellow"]
    assert len(body["products"]) == 4
    assert body["dataStale"] is False
    assert body["staleInfo"] is None

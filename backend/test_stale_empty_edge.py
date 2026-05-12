"""Phase 81 (v1.25 QA-08) — staleAll + empty products edge case.

Documents the existing behavior when `proposals.json` has empty
products but source files have current mtime (isStale=false).

Scenario: fresh deploy where scheduler hasn't produced any scrape
output yet but source files were created with mtime=now (e.g. `touch`
or empty write). `_build_source_freshness` reports all 3 colors as
fresh → `staleAll` is absent → UI shows empty-state message.

v1.24 verifier called this out as "the original bug reappearing
through a different door" — but the scenario is distinct from the
pool-outage empty grid (which v1.24 Phase 78 fixed). This test
PINS the current behavior so future changes don't silently alter it.

If/when we want UI to say "scheduler has not yet produced data"
instead of "no products in category", add that logic under a new
diagnostic field (e.g. `emptyReason: "scheduler_never_ran"`) and
update this test — don't conflate it with the staleAll path.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backend.main as main


def _seed_fresh_deploy(tmp_path, monkeypatch):
    """Create source files with current mtime + empty proposals.json."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Empty products list
    (data_dir / "proposals.json").write_text(json.dumps({
        "updatedAt": "2026-05-13 00:00:00",
        "products": [],
    }), encoding="utf-8")

    # All 3 source files exist + have current mtime but are empty
    for color in ("green", "red", "yellow"):
        (data_dir / f"{color}_products.json").write_text(
            json.dumps({"products": []}),
            encoding="utf-8",
        )

    monkeypatch.setattr(main, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(main, "PROPOSALS_PATH", str(data_dir / "proposals.json"))
    return data_dir


def _patch_freshness_all_fresh(monkeypatch):
    """Monkeypatch _build_source_freshness to return all-fresh state."""
    source_freshness = {}
    for color in ("green", "red", "yellow"):
        source_freshness[color] = {
            "exists": True,
            "updatedAt": "2026-05-13T00:00:00",
            "ageMinutes": 1.0,  # very fresh
            "isStale": False,
            "status": "ok",
        }
    latest_mtime = 1_778_000_000.0

    def _fake(stale_minutes: int = 10):
        return source_freshness, [], latest_mtime

    monkeypatch.setattr(main, "_build_source_freshness", _fake)


def test_fresh_deploy_empty_products_returns_dataStale_false(
    tmp_path, monkeypatch
):
    """Fresh deploy: empty products + fresh mtime → dataStale=false,
    no staleAll block, empty products list returned.

    This is the current behavior. The v1.24 verifier flagged it as
    a documented gap — UI shows "В этой категории пока нет товаров"
    which is misleading when the real cause is "scheduler hasn't run
    yet", not "no products in this filter". Fix belongs in v1.26+.
    """
    _seed_fresh_deploy(tmp_path, monkeypatch)
    _patch_freshness_all_fresh(monkeypatch)

    client = TestClient(main.app)
    resp = client.get("/api/products")
    assert resp.status_code == 200
    body = resp.json()

    # Empty products
    assert body["products"] == []

    # Not stale — source files are fresh (even though they contain nothing)
    assert body["dataStale"] is False

    # No staleAll block — this is NOT the pool-outage scenario
    assert body.get("staleAll") is None


def test_fresh_deploy_partial_sources_still_no_staleAll(
    tmp_path, monkeypatch
):
    """Fresh deploy with only 1 stale source (e.g. green scraper never
    ran) keeps v1.22 phantom-strip behavior: that color is filtered,
    but no staleAll block fires because not all 3 are stale."""
    _seed_fresh_deploy(tmp_path, monkeypatch)

    # Seed a product so the filter has something to strip
    data_dir = tmp_path / "data"
    (data_dir / "proposals.json").write_text(json.dumps({
        "updatedAt": "2026-05-13 00:00:00",
        "products": [
            {
                "id": "g1", "name": "Green Apple", "url": "https://x",
                "currentPrice": "10", "oldPrice": "20", "image": "", "stock": 1,
                "unit": "шт", "category": "Fruit", "type": "green",
            },
            {
                "id": "r1", "name": "Red Apple", "url": "https://x",
                "currentPrice": "12", "oldPrice": "22", "image": "", "stock": 1,
                "unit": "шт", "category": "Fruit", "type": "red",
            },
        ],
    }), encoding="utf-8")

    # Green stale, red+yellow fresh
    def _fake_partial(stale_minutes: int = 10):
        return {
            "green": {"isStale": True, "ageMinutes": 30.0, "status": "stale", "updatedAt": "x"},
            "red": {"isStale": False, "ageMinutes": 2.0, "status": "ok", "updatedAt": "y"},
            "yellow": {"isStale": False, "ageMinutes": 2.0, "status": "ok", "updatedAt": "z"},
        }, ["green (30m)"], 1_778_000_000.0

    monkeypatch.setattr(main, "_build_source_freshness", _fake_partial)

    client = TestClient(main.app)
    resp = client.get("/api/products")
    body = resp.json()

    # Green stripped (v1.22 behavior preserved)
    types = [p["type"] for p in body["products"]]
    assert "green" not in types
    assert "red" in types

    # No staleAll because only 1 of 3 stale
    assert body.get("staleAll") is None
    # But dataStale is True because staleInfo is non-empty
    assert body["dataStale"] is True

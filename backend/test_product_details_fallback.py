import json
from pathlib import Path

import requests
from fastapi.testclient import TestClient

import backend.main as main


client = TestClient(main.app)


def test_product_details_returns_fallback_payload_on_upstream_timeout(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "proposals.json").write_text(
        json.dumps(
            {
                "products": [
                    {
                        "id": "42",
                        "url": "https://vkusvill.ru/goods/test-42.html",
                        "weight": "500 г",
                        "image": "https://img.example/test.webp",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(main, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(main, "_vkusvill_backoff_until", 0.0)

    def boom(*args, **kwargs):
        raise requests.ConnectTimeout("timeout")

    monkeypatch.setattr(requests, "get", boom)

    response = client.get("/api/product/42/details")

    assert response.status_code == 200
    assert response.json() == {
        "id": "42",
        "weight": "500 г",
        "description": "",
        "shelf_life": "",
        "storage": "",
        "composition": "",
        "nutrition": "",
        "images": ["https://img.example/test.webp"],
        "source_unavailable": True,
        "source_error": "timeout",
    }


def test_product_details_uses_backoff_after_first_upstream_timeout(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "proposals.json").write_text(
        json.dumps(
            {
                "products": [
                    {
                        "id": "42",
                        "url": "https://vkusvill.ru/goods/test-42.html",
                        "weight": "",
                        "image": "",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    calls = {"count": 0}

    def boom(*args, **kwargs):
        calls["count"] += 1
        raise requests.ConnectTimeout("timeout")

    monkeypatch.setattr(main, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(main, "_vkusvill_backoff_until", 0.0)
    monkeypatch.setattr(requests, "get", boom)

    first = client.get("/api/product/42/details")
    second = client.get("/api/product/42/details")

    assert first.status_code == 200
    assert second.status_code == 200
    assert calls["count"] == 1
    assert second.json()["source_unavailable"] is True

import json
import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backend.main as main
import scrape_catalog_discovery as discovery


client = TestClient(main.app)


ROOT_HTML = """
<div class="VVCategCards2020__Row _compact">
  <div class="VVCategCards2020__Col">
    <a class="VVCategCards2020__Item" href="/goods/gotovaya-eda/">Готовая еда</a>
  </div>
  <div class="VVCategCards2020__Col">
    <a class="VVCategCards2020__Item" href="/goods/postnoe-i-vegetarianskoe/">Постное и вегетарианское</a>
  </div>
</div>
"""

SOURCE_HTML = """
<html><body>
<h1>Готовая еда</h1>
<div>1418 товаров</div>
<div class="ProductCard">
  <a class="ProductCard__imageLink" href="/goods/salat-tsezar-61483.html"></a>
  <a class="ProductCard__link" href="/goods/salat-tsezar-61483.html">Салат Цезарь</a>
  <img src="https://img.example/61483.webp" />
</div>
<div class="ProductCard">
  <a class="ProductCard__link" href="/goods/sendvich-roll-tsezar-20542.html">Сэндвич ролл Цезарь</a>
</div>
<a href="/goods/gotovaya-eda/?PAGEN_1=2">2</a>
<a href="/goods/gotovaya-eda/?PAGEN_1=4">4</a>
</body></html>
"""


class DummyThread:
    def __init__(self, target=None, daemon=None):
        self.target = target
        self.daemon = daemon

    def start(self):
        return None


def test_discover_catalog_sources_from_root_tiles():
    sources = discovery.discover_catalog_sources_from_html(ROOT_HTML)
    assert [source["slug"] for source in sources] == [
        "gotovaya-eda",
        "postnoe-i-vegetarianskoe",
    ]


def test_extract_source_count_and_max_page():
    assert discovery.extract_source_count_from_html(SOURCE_HTML) == 1418
    assert discovery.extract_max_page_from_html(SOURCE_HTML) == 4


def test_extract_numeric_product_id():
    assert discovery.extract_numeric_product_id("https://vkusvill.ru/goods/salat-tsezar-61483.html") == "61483"
    assert discovery.extract_numeric_product_id("https://vkusvill.ru/goods/gotovaya-eda/") is None


def test_build_source_state_stays_incomplete_on_mismatch():
    source = {"name": "Готовая еда", "slug": "gotovaya-eda", "url": "https://vkusvill.ru/goods/gotovaya-eda/"}
    entry = discovery.build_source_state_entry(
        source=source,
        expected_count=10,
        current_run_count=8,
        stored_count=9,
        complete=False,
        last_error="count mismatch: expected 10, collected 8",
        last_failed_page=2,
        last_run_at="2026-04-04T00:00:00+00:00",
    )
    assert entry["complete"] is False
    assert entry["expected_count"] == 10
    assert entry["collected_count"] == 8
    assert entry["stored_count"] == 9


def test_merge_source_products_preserves_existing_items_on_incomplete_rerun():
    existing = {
        "61483": {
            "product_id": "61483",
            "name": "Салат Цезарь",
            "url": "https://vkusvill.ru/goods/salat-tsezar-61483.html",
            "image_url": "",
            "first_seen_at": "old",
            "last_seen_at": "old",
        },
        "20542": {
            "product_id": "20542",
            "name": "Сэндвич ролл Цезарь",
            "url": "https://vkusvill.ru/goods/sendvich-roll-tsezar-20542.html",
            "image_url": "",
            "first_seen_at": "old",
            "last_seen_at": "old",
        },
    }
    new_products = [
        {
            "product_id": "61483",
            "name": "Салат Цезарь",
            "url": "https://vkusvill.ru/goods/salat-tsezar-61483.html",
            "image_url": "https://img.example/61483.webp",
        }
    ]
    merged = discovery.merge_source_products(existing, new_products, "now")
    assert set(merged.keys()) == {"61483", "20542"}
    assert merged["61483"]["image_url"] == "https://img.example/61483.webp"
    assert merged["20542"]["name"] == "Сэндвич ролл Цезарь"


def test_parse_source_products_rejects_cards_without_numeric_identity():
    html = """
    <div class="ProductCard">
      <a class="ProductCard__link" href="/goods/gotovaya-eda/">No stable id</a>
    </div>
    """
    products, invalid_count = discovery.parse_source_products_from_html(html, "https://vkusvill.ru/goods/gotovaya-eda/")
    assert products == []
    assert invalid_count == 1


def test_catalog_discovery_status_route_returns_state(monkeypatch, tmp_path):
    state_path = tmp_path / "catalog_discovery_state.json"
    state_path.write_text(
        json.dumps(
            {
                "updated_at": "2026-04-04T00:00:00+00:00",
                "sources": {
                    "gotovaya-eda": {
                        "expected_count": 1418,
                        "collected_count": 1409,
                        "complete": False,
                        "last_error": "count mismatch",
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(main, "CATALOG_DISCOVERY_STATE_PATH", str(state_path))

    response = client.get("/api/admin/run/catalog-discovery/status")

    assert response.status_code == 200
    body = response.json()
    assert "state" in body
    assert body["state"]["sources"]["gotovaya-eda"]["complete"] is False


def test_catalog_discovery_run_route_starts(monkeypatch):
    previous = dict(main.scraper_status["catalog_discovery"])
    main.scraper_status["catalog_discovery"] = {
        "running": False,
        "last_run": None,
        "exit_code": None,
        "last_output": "",
    }
    monkeypatch.setattr(main.threading, "Thread", DummyThread)
    try:
        response = client.post("/api/admin/run/catalog-discovery")
        assert response.status_code == 200
        assert response.json()["started"] == "catalog_discovery"
    finally:
        main.scraper_status["catalog_discovery"] = previous

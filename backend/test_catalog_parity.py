import os
import sys
import sqlite3

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backend.main as main
import backend.prediction as prediction
from database.db import Database


client = TestClient(main.app)


def _setup_history_db(monkeypatch, tmp_path):
    db_path = str(tmp_path / "history.db")
    test_db = Database(db_path)
    monkeypatch.setattr(main, "db", test_db)
    monkeypatch.setattr(main, "_get_scraped_image_map", lambda: {})
    monkeypatch.setattr(prediction, "get_batch_predictions", lambda product_ids: {})
    return db_path


def test_discovery_backfilled_blank_taxonomy_product_is_searchable(monkeypatch, tmp_path):
    db_path = _setup_history_db(monkeypatch, tmp_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO product_catalog (
            product_id, name, category, group_name, subgroup, image_url,
            last_known_price, total_sale_count, last_sale_at, last_sale_type,
            avg_discount_pct, max_discount_pct, usual_sale_time, avg_catch_window_min, updated_at
        ) VALUES (?, ?, '', '', '', ?, 0, 0, NULL, NULL, 0, 0, NULL, 0, '2026-04-04T00:00:00+03:00')
        """,
        (
            "18920",
            "Омуль подкопченный ломтики, 100 г",
            "https://img.example/18920.webp",
        ),
    )
    conn.commit()
    conn.close()

    response = client.get(
        "/api/history/products",
        params={"search": "Омуль подкопченный ломтики, 100 г", "page": 1, "per_page": 20},
    )

    assert response.status_code == 200
    body = response.json()
    ids = [product["id"] for product in body["products"]]
    assert "18920" in ids
    product = next(product for product in body["products"] if product["id"] == "18920")
    assert product["image_url"] == "https://img.example/18920.webp"
    assert product["total_sale_count"] == 0

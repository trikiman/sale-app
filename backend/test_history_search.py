import sqlite3
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

import backend.main as main
import backend.prediction as prediction
from database.db import Database


client = TestClient(main.app)


def _insert_product(
    db_path,
    product_id,
    name,
    category,
    group_name,
    subgroup,
    total_sale_count,
    last_sale_at,
    last_sale_type,
):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO product_catalog (
            product_id, name, category, group_name, subgroup, image_url,
            last_known_price, total_sale_count, last_sale_at, last_sale_type,
            avg_discount_pct, max_discount_pct, usual_sale_time, avg_catch_window_min, updated_at
        ) VALUES (?, ?, ?, ?, ?, '', 199, ?, ?, ?, 20, 25, '09:00', 45, '2026-04-04T00:00:00+03:00')
        """,
        (
            product_id,
            name,
            category,
            group_name,
            subgroup,
            total_sale_count,
            last_sale_at,
            last_sale_type,
        ),
    )
    conn.commit()
    conn.close()


def _insert_session(db_path, product_id, sale_type, is_active, old_price):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO sale_sessions (
            product_id, sale_type, price, old_price, discount_pct,
            first_seen, last_seen, duration_minutes, is_active
        ) VALUES (?, ?, 149, ?, 20, '2026-04-04T00:00:00+03:00', '2026-04-04T00:00:00+03:00', 30, ?)
        """,
        (product_id, sale_type, old_price, is_active),
    )
    conn.commit()
    conn.close()


def _response_ids(response_json):
    return [product["id"] for product in response_json["products"]]


def _setup_history_db(monkeypatch, tmp_path):
    db_path = str(tmp_path / "history.db")
    test_db = Database(db_path)
    monkeypatch.setattr(main, "db", test_db)
    monkeypatch.setattr(main, "_get_scraped_image_map", lambda: {})
    monkeypatch.setattr(prediction, "get_batch_predictions", lambda product_ids: {})
    return db_path


def test_history_search_returns_live_history_and_catalog_matches(monkeypatch, tmp_path):
    db_path = _setup_history_db(monkeypatch, tmp_path)

    _insert_product(
        db_path,
        "live-1",
        "салат цезарь свежий",
        "Готовая еда",
        "Готовая еда",
        "Салаты",
        3,
        "2026-04-04T00:00:00+03:00",
        "green",
    )
    _insert_product(
        db_path,
        "history-1",
        "сэндвич цезарь",
        "Готовая еда",
        "Готовая еда",
        "Сэндвичи",
        2,
        "2026-04-03T00:00:00+03:00",
        "red",
    )
    _insert_product(
        db_path,
        "catalog-1",
        "соус цезарь фирменный",
        "Соусы",
        "Соусы",
        "Белые соусы",
        0,
        None,
        None,
    )
    _insert_product(
        db_path,
        "other-1",
        "Борщ домашний",
        "Супы",
        "Готовая еда",
        "Супы",
        1,
        "2026-04-02T00:00:00+03:00",
        "yellow",
    )

    _insert_session(db_path, "live-1", "green", 1, 249)
    _insert_session(db_path, "history-1", "red", 0, 219)
    _insert_session(db_path, "other-1", "yellow", 0, 180)

    search_response = client.get("/api/history/products", params={"search": "цезарь", "page": 1, "per_page": 20})
    assert search_response.status_code == 200

    search_ids = set(_response_ids(search_response.json()))
    assert search_ids == {"live-1", "history-1", "catalog-1"}

    product_map = {product["id"]: product for product in search_response.json()["products"]}
    assert product_map["live-1"]["is_currently_on_sale"] is True
    assert product_map["live-1"]["last_old_price"] == 249
    assert product_map["catalog-1"]["total_sale_count"] == 0
    assert product_map["catalog-1"]["is_currently_on_sale"] is False

    default_response = client.get("/api/history/products", params={"page": 1, "per_page": 20})
    assert default_response.status_code == 200
    assert "catalog-1" not in _response_ids(default_response.json())


def test_fuzzy_search_respects_group_and_subgroup_filters(monkeypatch, tmp_path):
    db_path = _setup_history_db(monkeypatch, tmp_path)

    _insert_product(
        db_path,
        "live-1",
        "салат цезарь свежий",
        "Готовая еда",
        "Готовая еда",
        "Салаты",
        3,
        "2026-04-04T00:00:00+03:00",
        "green",
    )
    _insert_product(
        db_path,
        "history-1",
        "сэндвич цезарь",
        "Готовая еда",
        "Готовая еда",
        "Сэндвичи",
        1,
        "2026-04-03T00:00:00+03:00",
        "red",
    )
    _insert_product(
        db_path,
        "catalog-1",
        "соус цезарь фирменный",
        "Соусы",
        "Соусы",
        "Белые соусы",
        0,
        None,
        None,
    )

    _insert_session(db_path, "live-1", "green", 1, 249)
    _insert_session(db_path, "history-1", "red", 0, 219)

    response = client.get(
        "/api/history/products",
        params={
            "search": "цезерь",
            "group": "Готовая еда",
            "subgroup": "Салаты",
            "page": 1,
            "per_page": 20,
        },
    )

    assert response.status_code == 200
    assert _response_ids(response.json()) == ["live-1"]


def test_groups_scope_all_includes_catalog_only_groups(monkeypatch, tmp_path):
    db_path = _setup_history_db(monkeypatch, tmp_path)

    _insert_product(
        db_path,
        "history-1",
        "сэндвич цезарь",
        "Готовая еда",
        "Готовая еда",
        "Сэндвичи",
        1,
        "2026-04-03T00:00:00+03:00",
        "red",
    )
    _insert_product(
        db_path,
        "catalog-1",
        "соус цезарь фирменный",
        "Соусы",
        "Соусы",
        "Белые соусы",
        0,
        None,
        None,
    )

    history_groups = client.get("/api/groups", params={"scope": "history"})
    all_groups = client.get("/api/groups", params={"scope": "all"})

    assert history_groups.status_code == 200
    assert all_groups.status_code == 200

    history_names = {group["name"] for group in history_groups.json()["groups"]}
    all_names = {group["name"] for group in all_groups.json()["groups"]}

    assert "Готовая еда" in history_names
    assert "Соусы" not in history_names
    assert "Соусы" in all_names


def test_history_search_matches_uppercase_cyrillic_names(monkeypatch, tmp_path):
    db_path = _setup_history_db(monkeypatch, tmp_path)

    _insert_product(
        db_path,
        "catalog-upper",
        'Салат "Цезарь" с курицей',
        "Готовая еда",
        "Готовая еда",
        "Салаты",
        0,
        None,
        None,
    )

    response = client.get(
        "/api/history/products",
        params={"search": "цезарь", "page": 1, "per_page": 20},
    )

    assert response.status_code == 200
    assert "catalog-upper" in _response_ids(response.json())


def test_history_search_matches_multiword_queries_regardless_of_word_order(monkeypatch, tmp_path):
    db_path = _setup_history_db(monkeypatch, tmp_path)

    _insert_product(
        db_path,
        "catalog-order",
        'Салат "Цезарь" с курицей',
        "Готовая еда",
        "Готовая еда",
        "Салаты",
        0,
        None,
        None,
    )

    response = client.get(
        "/api/history/products",
        params={"search": "цезарь салат", "page": 1, "per_page": 20},
    )

    assert response.status_code == 200
    assert "catalog-order" in _response_ids(response.json())


def test_history_search_matches_inflected_multiword_queries(monkeypatch, tmp_path):
    db_path = _setup_history_db(monkeypatch, tmp_path)

    _insert_product(
        db_path,
        "catalog-shrimp",
        'Салат "Цезарь" с креветками',
        "Готовая еда",
        "Готовая еда",
        "Салаты",
        0,
        None,
        None,
    )

    response = client.get(
        "/api/history/products",
        params={"search": "цезарь салат креветки", "page": 1, "per_page": 20},
    )

    assert response.status_code == 200
    assert "catalog-shrimp" in _response_ids(response.json())

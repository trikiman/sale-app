import json

from backend.notifier import Notifier
from database.db import Database


def _insert_catalog_row(db_path, product_id, name, category, group_name, subgroup):
    import sqlite3

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO product_catalog (
            product_id, name, category, group_name, subgroup, image_url,
            last_known_price, total_sale_count, last_sale_at, last_sale_type,
            avg_discount_pct, max_discount_pct, usual_sale_time, avg_catch_window_min, updated_at
        ) VALUES (?, ?, ?, ?, ?, '', 100, 1, '2026-04-03T09:00:00+03:00', 'red', 20, 20, '09:00', 30, '2026-04-03T09:00:00+03:00')
        """,
        (product_id, name, category, group_name, subgroup),
    )
    conn.commit()
    conn.close()


def test_group_and_subgroup_favorites_dedupe_with_catalog_fallback(tmp_path):
    db_path = str(tmp_path / "test.db")
    proposals_path = tmp_path / "proposals.json"

    db = Database(db_path)
    db.upsert_user(101, first_name="Test")
    db.add_favorite_product(101, "p1", "Dog Food Deluxe")
    db.add_favorite_category(101, "group:Pet Care", "Pet Care")
    db.add_favorite_category(101, "subgroup:Pet Care/Dogs", "Dogs")
    db.record_notification(101, "p2")

    _insert_catalog_row(db_path, "p1", "Dog Food Deluxe", "Pet Care", "Pet Care", "Dogs")
    _insert_catalog_row(db_path, "p2", "Dog Toy Rope", "Pet Care", "Pet Care", "")
    _insert_catalog_row(db_path, "p3", "Cat Snack", "Pet Care", "Pet Care", "Cats")
    _insert_catalog_row(db_path, "p4", "Dog Bed", "Pet Care", "Pet Care", "")

    proposals_path.write_text(
        json.dumps(
            {
                "products": [
                    {
                        "id": "p1",
                        "name": "Dog Food Deluxe",
                        "currentPrice": "100",
                        "oldPrice": "150",
                        "stock": 5,
                        "unit": "шт",
                        "type": "red",
                        "url": "https://example.com/p1",
                        "category": "Pet Care",
                    },
                    {
                        "id": "p2",
                        "name": "Dog Toy Rope",
                        "currentPrice": "80",
                        "oldPrice": "120",
                        "stock": 4,
                        "unit": "шт",
                        "type": "red",
                        "url": "https://example.com/p2",
                        "category": "Pet Care",
                    },
                    {
                        "id": "p3",
                        "name": "Cat Snack",
                        "currentPrice": "60",
                        "oldPrice": "90",
                        "stock": 3,
                        "unit": "шт",
                        "type": "yellow",
                        "url": "https://example.com/p3",
                        "category": "Pet Care",
                    },
                    {
                        "id": "p4",
                        "name": "Dog Bed",
                        "currentPrice": "200",
                        "oldPrice": "260",
                        "stock": 2,
                        "unit": "шт",
                        "type": "green",
                        "url": "https://example.com/p4",
                        "category": "Pet Care",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    notifier = Notifier(bot_token="")
    notifier.db = db
    notifier.proposals_path = str(proposals_path)

    alerts = notifier.get_favorite_alerts()
    assert 101 in alerts

    by_id = {entry["product"]["id"]: entry for entry in alerts[101]}
    assert set(by_id) == {"p1", "p3", "p4"}
    assert by_id["p1"]["match_reason"]["kind"] == "subgroup"
    assert by_id["p3"]["match_reason"]["kind"] == "group"
    assert by_id["p4"]["match_reason"]["kind"] == "group"
    assert "p2" not in by_id

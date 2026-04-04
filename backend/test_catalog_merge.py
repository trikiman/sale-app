import json
import os
import sys
import sqlite3
import builtins
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import merge_catalog_discovery as merge_mod
import database.sale_history as sale_history


def test_merge_source_product_maps_dedupes_and_preserves_source_memberships(tmp_path):
    source_dir = tmp_path / "sources"
    source_dir.mkdir()

    state_doc = {
        "sources": {
            "a": {"complete": True},
            "b": {"complete": True},
        }
    }
    (source_dir / "a.json").write_text(
        json.dumps(
            {
                "source_name": "A",
                "products": {
                    "1": {"name": "Milk", "url": "u1", "image_url": "img1"},
                    "2": {"name": "Bread", "url": "u2", "image_url": ""},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (source_dir / "b.json").write_text(
        json.dumps(
            {
                "source_name": "B",
                "products": {
                    "1": {"name": "Milk", "url": "u1b", "image_url": ""},
                    "3": {"name": "Cheese", "url": "u3", "image_url": "img3"},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    merged = merge_mod.merge_source_product_maps(state_doc, str(source_dir))
    assert set(merged.keys()) == {"1", "2", "3"}
    assert merged["1"]["image_url"] == "img1"
    assert merged["1"]["source_slugs"] == ["a", "b"]


def test_merge_into_category_products_preserves_existing_taxonomy():
    existing = {
        "1": {
            "name": "Milk",
            "category": "Молочные продукты",
            "group": "Молочные продукты, яйцо",
            "subgroups": ["Молоко"],
            "image_url": "",
        }
    }
    merged = {
        "1": {
            "product_id": "1",
            "name": "Milk",
            "url": "u1",
            "image_url": "img1",
            "source_slugs": ["s1"],
            "source_names": ["Source 1"],
        },
        "2": {
            "product_id": "2",
            "name": "New Product",
            "url": "u2",
            "image_url": "img2",
            "source_slugs": ["s2"],
            "source_names": ["Source 2"],
        },
    }

    updated, added, changed = merge_mod.merge_into_category_products(existing, merged)
    assert added == 1
    assert changed == 1
    assert updated["1"]["group"] == "Молочные продукты, яйцо"
    assert updated["1"]["subgroups"] == ["Молоко"]
    assert updated["1"]["image_url"] == "img1"
    assert updated["2"]["name"] == "New Product"
    assert updated["2"]["image_url"] == "img2"
    assert updated["2"]["discovery_sources"] == ["s2"]


def test_seed_product_catalog_backfills_image_url(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    category_db_path = data_dir / "category_db.json"
    category_db_path.write_text(
        json.dumps(
            {
                "products": {
                    "100": {
                        "name": "Discovered Product",
                        "category": "",
                        "group": "",
                        "subgroups": [],
                        "image_url": "https://img.example/100.webp",
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    db_path = data_dir / "test.db"
    monkeypatch.setattr(config, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    monkeypatch.setattr(builtins, "print", lambda *args, **kwargs: None)

    sale_history.init_sale_history_tables()
    sale_history.seed_product_catalog()

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT product_id, name, image_url FROM product_catalog WHERE product_id = '100'")
    row = cur.fetchone()
    conn.close()

    assert row == ("100", "Discovered Product", "https://img.example/100.webp")

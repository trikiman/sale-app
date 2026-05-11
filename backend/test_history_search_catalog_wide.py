"""v1.22 Phase 70 UX-BUG-01 — history search catalog-wide + currentSaleType.

Covers:
  * ``_load_current_sale_types`` — defensive loader over PROPOSALS_PATH
  * ``/api/history/products`` — row enrichment with ``currentSaleType`` and
    upgraded ``is_currently_on_sale`` signal that unions sale_sessions with
    today's proposals.

Unit-only (no HTTP, no Vercel). Live verification via
``scripts/verify_v1.22.sh 70`` + ``70-VERIFICATION.md`` MCP step.
"""
from __future__ import annotations

import json
import sqlite3

import pytest

import backend.main as bm


# ── _load_current_sale_types ──────────────────────────────────────────────


def test_load_current_sale_types_empty_on_missing_file(tmp_path, monkeypatch):
    """Missing proposals.json → empty dict, no exception."""
    monkeypatch.setattr(bm, "PROPOSALS_PATH", str(tmp_path / "nope.json"))
    assert bm._load_current_sale_types() == {}


def test_load_current_sale_types_empty_on_malformed(tmp_path, monkeypatch):
    """Malformed JSON → empty dict, no exception."""
    p = tmp_path / "proposals.json"
    p.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(bm, "PROPOSALS_PATH", str(p))
    assert bm._load_current_sale_types() == {}


def test_load_current_sale_types_maps_id_to_type(tmp_path, monkeypatch):
    """Valid proposals.json → {str(id): type} map for green/red/yellow only."""
    p = tmp_path / "proposals.json"
    p.write_text(
        json.dumps(
            {
                "products": [
                    {"id": 1001, "type": "green"},
                    {"id": 1002, "type": "red"},
                    {"id": 1003, "type": "yellow"},
                    {"id": 1004, "type": "other"},      # skipped (bad type)
                    {"id": None, "type": "green"},       # skipped (no id)
                    {"id": 1005, "type": None},          # skipped (no type)
                    {"id": 1006},                        # skipped (no type key)
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(bm, "PROPOSALS_PATH", str(p))
    result = bm._load_current_sale_types()
    assert result == {"1001": "green", "1002": "red", "1003": "yellow"}


# ── /api/history/products currentSaleType enrichment ──────────────────────


def _seed_test_db(tmp_path) -> str:
    """Create a throwaway sqlite DB with minimal product_catalog + sale_sessions."""
    dbp = tmp_path / "test_history.db"
    conn = sqlite3.connect(str(dbp))
    c = conn.cursor()
    c.execute(
        """CREATE TABLE product_catalog (
            product_id INTEGER PRIMARY KEY,
            name TEXT,
            category TEXT,
            group_name TEXT,
            subgroup TEXT,
            image_url TEXT,
            last_known_price REAL,
            total_sale_count INTEGER,
            last_sale_at TEXT,
            last_sale_type TEXT,
            avg_discount_pct REAL,
            max_discount_pct REAL,
            usual_sale_time TEXT,
            avg_catch_window_min REAL
        )"""
    )
    c.execute(
        """CREATE TABLE sale_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            is_active INTEGER,
            old_price REAL
        )"""
    )
    # Product 2001: zero history, currently live in proposals as green.
    c.execute(
        "INSERT INTO product_catalog VALUES "
        "(2001, 'Салат Цезарь классический', 'cat', 'Готовая еда', NULL, NULL, 299, 0, NULL, NULL, 0, 0, NULL, 0)"
    )
    # Product 2002: historical yellow, NOT in proposals.
    c.execute(
        "INSERT INTO product_catalog VALUES "
        "(2002, 'Ролл Цезарь куриный', 'cat', 'Готовая еда', NULL, NULL, 199, 5, '2026-05-01', 'yellow', 15, 25, NULL, 30)"
    )
    conn.commit()
    conn.close()
    return str(dbp)


def test_history_search_exposes_current_sale_type_for_live_product(
    tmp_path, monkeypatch
):
    """Fixture: product 2001 has zero sale_sessions AND zero history, but IS in
    today's proposals as green. Search should return it with
    currentSaleType='green' AND is_currently_on_sale=True."""
    dbp = _seed_test_db(tmp_path)
    proposals = tmp_path / "proposals.json"
    proposals.write_text(
        json.dumps({"products": [{"id": 2001, "type": "green"}]}),
        encoding="utf-8",
    )

    monkeypatch.setattr(bm, "PROPOSALS_PATH", str(proposals))
    monkeypatch.setattr(bm.db, "db_path", dbp)

    response = bm.history_get_products(
        page=1,
        per_page=50,
        search="цезарь",
        category=None,
        group=None,
        subgroup=None,
        filter=None,
        sort="last_seen",
        x_telegram_user_id=None,
    )

    # Both products match "цезарь" — filter is removed in search mode.
    assert response["total"] >= 2
    by_id = {p["id"]: p for p in response["products"]}

    # Product 2001 is live in proposals → currentSaleType=green + is_currently_on_sale=True
    assert 2001 in by_id, "live product 2001 missing from search results"
    assert by_id[2001]["currentSaleType"] == "green"
    assert by_id[2001]["is_currently_on_sale"] is True

    # Product 2002 is history-only → currentSaleType=None, last_sale_type preserved
    assert 2002 in by_id, "history product 2002 missing from search results"
    assert by_id[2002]["currentSaleType"] is None
    assert by_id[2002]["last_sale_type"] == "yellow"


def test_history_search_currentsaletype_null_when_proposals_empty(
    tmp_path, monkeypatch
):
    """Empty proposals.json → currentSaleType=None for ALL rows."""
    dbp = _seed_test_db(tmp_path)
    proposals = tmp_path / "proposals.json"
    proposals.write_text(json.dumps({"products": []}), encoding="utf-8")

    monkeypatch.setattr(bm, "PROPOSALS_PATH", str(proposals))
    monkeypatch.setattr(bm.db, "db_path", dbp)

    response = bm.history_get_products(
        page=1,
        per_page=50,
        search="цезарь",
        category=None,
        group=None,
        subgroup=None,
        filter=None,
        sort="last_seen",
        x_telegram_user_id=None,
    )

    for p in response["products"]:
        assert p["currentSaleType"] is None
    # And is_currently_on_sale falls back to sale_sessions only
    # (both fixture products have no active sessions, so both are False).
    for p in response["products"]:
        assert p["is_currently_on_sale"] is False

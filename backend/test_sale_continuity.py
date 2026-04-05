import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

import backend.main as main
import config
import database.sale_history as sale_history
from database.db import Database


client = TestClient(main.app)


def _product(pid: str, sale_type: str = "green") -> dict:
    return {
        "id": pid,
        "name": f"Product {pid}",
        "type": sale_type,
        "currentPrice": "100",
        "oldPrice": "200",
        "image": "",
        "category": "test",
        "group": "Test Group",
        "subgroup": "Test Subgroup",
    }


def _write_cycle_state(data_dir: Path, *, green: bool, red: bool = False, yellow: bool = False):
    def _entry(counted: bool, label: str):
        return {
            "status": "ok" if counted else "timeout",
            "status_text": "OK (data updated)" if counted else f"{label} skipped/failed",
            "counted_for_continuity": counted,
        }

    payload = {
        "sources": {
            "green": _entry(green, "green"),
            "red": _entry(red, "red"),
            "yellow": _entry(yellow, "yellow"),
        }
    }
    (data_dir / "scrape_cycle_state.json").write_text(json.dumps(payload), encoding="utf-8")


def _set_session_times(db_path: Path, product_id: str, *, first_seen: datetime, last_seen: datetime):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE sale_sessions
        SET first_seen = ?, last_seen = ?
        WHERE product_id = ? AND is_active = 1
        """,
        (first_seen.isoformat(), last_seen.isoformat(), product_id),
    )
    conn.commit()
    conn.close()


def _get_sessions(db_path: Path, product_id: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT product_id, is_active, first_seen, last_seen, new_entry_pending
        FROM sale_sessions
        WHERE product_id = ?
        ORDER BY id
        """,
        (product_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def _setup_env(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    db_path = tmp_path / "test.db"

    monkeypatch.setattr(config, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    monkeypatch.setattr(sale_history.config, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(sale_history.config, "DATABASE_PATH", str(db_path))
    monkeypatch.setattr(sale_history, "CYCLE_STATE_PATH", str(data_dir / "scrape_cycle_state.json"))
    monkeypatch.setattr(main, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(main, "PROPOSALS_PATH", str(data_dir / "proposals.json"))

    test_db = Database(str(db_path))
    monkeypatch.setattr(main, "db", test_db)
    return data_dir, Path(db_path), test_db


def test_unsafe_cycle_keeps_missing_product_active(monkeypatch, tmp_path):
    data_dir, db_path, _ = _setup_env(monkeypatch, tmp_path)

    _write_cycle_state(data_dir, green=True)
    sale_history.record_sale_appearances([_product("p1")])

    _write_cycle_state(data_dir, green=False)
    sale_history.record_sale_appearances([])

    sessions = _get_sessions(db_path, "p1")
    assert len(sessions) == 1
    assert sessions[0]["is_active"] == 1


def test_healthy_cycle_within_grace_window_keeps_session_active(monkeypatch, tmp_path):
    data_dir, db_path, _ = _setup_env(monkeypatch, tmp_path)

    _write_cycle_state(data_dir, green=True)
    sale_history.record_sale_appearances([_product("p1")])

    now = datetime.now(timezone.utc)
    _set_session_times(
        db_path,
        "p1",
        first_seen=now - timedelta(hours=2),
        last_seen=now - timedelta(minutes=59),
    )

    _write_cycle_state(data_dir, green=True)
    sale_history.record_sale_appearances([])

    sessions = _get_sessions(db_path, "p1")
    assert len(sessions) == 1
    assert sessions[0]["is_active"] == 1


def test_healthy_cycle_after_grace_window_closes_session_without_overwriting_last_seen(monkeypatch, tmp_path):
    data_dir, db_path, _ = _setup_env(monkeypatch, tmp_path)

    _write_cycle_state(data_dir, green=True)
    sale_history.record_sale_appearances([_product("p1")])

    now = datetime.now(timezone.utc)
    first_seen = now - timedelta(hours=3)
    last_seen = now - timedelta(minutes=61)
    _set_session_times(db_path, "p1", first_seen=first_seen, last_seen=last_seen)

    _write_cycle_state(data_dir, green=True)
    sale_history.record_sale_appearances([])

    sessions = _get_sessions(db_path, "p1")
    assert len(sessions) == 1
    assert sessions[0]["is_active"] == 0
    assert datetime.fromisoformat(sessions[0]["last_seen"]) == last_seen


def test_grace_window_reappearance_does_not_create_new_pending_entry(monkeypatch, tmp_path):
    data_dir, db_path, db = _setup_env(monkeypatch, tmp_path)

    _write_cycle_state(data_dir, green=True)
    sale_history.record_sale_appearances([_product("p1")])
    db.mark_pending_sale_entries_surfaced(["p1"])

    now = datetime.now(timezone.utc)
    _set_session_times(
        db_path,
        "p1",
        first_seen=now - timedelta(hours=2),
        last_seen=now - timedelta(minutes=59),
    )

    _write_cycle_state(data_dir, green=True)
    sale_history.record_sale_appearances([])
    sale_history.record_sale_appearances([_product("p1")])

    assert db.get_pending_sale_entry_products(["p1"]) == set()


def test_confirmed_reentry_opens_new_pending_entry_and_api_returns_it(monkeypatch, tmp_path):
    data_dir, db_path, db = _setup_env(monkeypatch, tmp_path)

    _write_cycle_state(data_dir, green=True)
    sale_history.record_sale_appearances([_product("p1")])
    db.mark_pending_sale_entries_surfaced(["p1"])

    now = datetime.now(timezone.utc)
    _set_session_times(
        db_path,
        "p1",
        first_seen=now - timedelta(hours=4),
        last_seen=now - timedelta(minutes=61),
    )

    _write_cycle_state(data_dir, green=True)
    sale_history.record_sale_appearances([])
    sale_history.record_sale_appearances([_product("p1")])

    proposals_path = data_dir / "proposals.json"
    proposals_path.write_text(json.dumps({"products": [_product("p1")]}), encoding="utf-8")

    sessions = _get_sessions(db_path, "p1")
    assert len(sessions) == 2
    assert sessions[-1]["is_active"] == 1
    assert sessions[-1]["new_entry_pending"] == 1

    response = client.get("/api/new-products")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["new_products"][0]["id"] == "p1"

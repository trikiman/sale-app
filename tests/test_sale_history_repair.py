import sqlite3
from pathlib import Path
import builtins

import config
import database.sale_history as sale_history


def _setup_env(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    db_path = tmp_path / "salebot.db"

    monkeypatch.setattr(config, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    monkeypatch.setattr(sale_history.config, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(sale_history.config, "DATABASE_PATH", str(db_path))
    monkeypatch.setattr(sale_history, "CYCLE_STATE_PATH", str(data_dir / "scrape_cycle_state.json"))
    monkeypatch.setattr(builtins, "print", lambda *args, **kwargs: None)

    sale_history.init_sale_history_tables()
    return data_dir, Path(db_path)


def _insert_session(db_path: Path, *, product_id: str, sale_type: str, first_seen: str, last_seen: str, active: int = 0, pending: int = 1):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO sale_sessions (
            product_id, sale_type, price, old_price, discount_pct,
            first_seen, last_seen, duration_minutes, is_active, new_entry_pending
        )
        VALUES (?, ?, 100, 200, 50, ?, ?, 0, ?, ?)
    """, (product_id, sale_type, first_seen, last_seen, active, pending))
    conn.commit()
    conn.close()


def _fetch_sessions(db_path: Path, product_id: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT product_id, sale_type, first_seen, last_seen, is_active, new_entry_pending
        FROM sale_sessions
        WHERE product_id = ?
        ORDER BY first_seen
    """, (product_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def test_repair_false_reentries_merges_short_gap_sessions(monkeypatch, tmp_path):
    _, db_path = _setup_env(monkeypatch, tmp_path)
    _insert_session(
        db_path,
        product_id="p1",
        sale_type="yellow",
        first_seen="2026-04-01T10:00:00+00:00",
        last_seen="2026-04-01T11:00:00+00:00",
    )
    _insert_session(
        db_path,
        product_id="p1",
        sale_type="yellow",
        first_seen="2026-04-01T11:05:00+00:00",
        last_seen="2026-04-01T12:00:00+00:00",
    )

    result = sale_history.repair_false_reentries(max_gap_minutes=60)

    rows = _fetch_sessions(db_path, "p1")
    assert result["merged_groups"] == 1
    assert result["removed_rows"] == 1
    assert len(rows) == 1
    assert rows[0]["first_seen"] == "2026-04-01T10:00:00+00:00"
    assert rows[0]["last_seen"] == "2026-04-01T12:00:00+00:00"
    assert rows[0]["new_entry_pending"] == 0


def test_repair_false_reentries_keeps_real_long_gap_sessions(monkeypatch, tmp_path):
    _, db_path = _setup_env(monkeypatch, tmp_path)
    _insert_session(
        db_path,
        product_id="p2",
        sale_type="green",
        first_seen="2026-04-01T10:00:00+00:00",
        last_seen="2026-04-01T11:00:00+00:00",
    )
    _insert_session(
        db_path,
        product_id="p2",
        sale_type="green",
        first_seen="2026-04-01T13:05:00+00:00",
        last_seen="2026-04-01T14:00:00+00:00",
    )

    result = sale_history.repair_false_reentries(max_gap_minutes=60)

    rows = _fetch_sessions(db_path, "p2")
    assert result["merged_groups"] == 0
    assert result["removed_rows"] == 0
    assert len(rows) == 2

"""
Sale History tracking for VkusVill Sale Monitor.
Records sale appearances and aggregates them into sessions.

Phase 13: HIST-01 (appearances), HIST-02 (sessions), HIST-03 (catalog)
"""
import json
import os
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

import config


# Gap threshold: if a product isn't seen for this many minutes,
# the session is considered closed and a new one starts.
SESSION_GAP_MINUTES = 15


def get_sale_db_path() -> str:
    """Return path to the main database."""
    return config.DATABASE_PATH


@contextmanager
def get_connection():
    """Get database connection with WAL mode and row_factory."""
    conn = sqlite3.connect(get_sale_db_path(), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_sale_history_tables():
    """Create sale history tables if they don't exist."""
    with get_connection() as conn:
        c = conn.cursor()

        # Sale appearances: every time a product is seen on sale
        c.execute("""
            CREATE TABLE IF NOT EXISTS sale_appearances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL,
                sale_type TEXT NOT NULL,
                price REAL,
                old_price REAL,
                discount_pct INTEGER,
                seen_at TEXT NOT NULL,
                UNIQUE(product_id, seen_at)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_appearances_product ON sale_appearances(product_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_appearances_seen ON sale_appearances(seen_at)")

        # Sale sessions: continuous availability windows
        c.execute("""
            CREATE TABLE IF NOT EXISTS sale_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL,
                sale_type TEXT NOT NULL,
                price REAL,
                old_price REAL,
                discount_pct INTEGER,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                duration_minutes INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_sessions_product ON sale_sessions(product_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_sessions_active ON sale_sessions(is_active)")

        # Product catalog: all known VkusVill products with sale stats
        c.execute("""
            CREATE TABLE IF NOT EXISTS product_catalog (
                product_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT,
                image_url TEXT,
                last_known_price REAL,
                total_sale_count INTEGER DEFAULT 0,
                last_sale_at TEXT,
                last_sale_type TEXT,
                avg_discount_pct REAL DEFAULT 0,
                max_discount_pct INTEGER DEFAULT 0,
                usual_sale_time TEXT,
                avg_catch_window_min REAL DEFAULT 0,
                updated_at TEXT NOT NULL
            )
        """)

        print("✅ Sale history tables initialized")


def calc_discount(current_price, old_price) -> int:
    """Calculate discount percentage."""
    try:
        cur = float(current_price) if current_price else 0
        old = float(old_price) if old_price else 0
        if old > 0 and cur > 0:
            return round((1 - cur / old) * 100)
    except (ValueError, TypeError):
        pass
    return 0


def record_sale_appearances(current_products: List[Dict[str, Any]]):
    """
    Record current sale products and manage sessions.
    Called after each scrape_merge cycle.
    
    Args:
        current_products: list of product dicts from proposals.json
                          Each has: id, name, type, currentPrice, oldPrice, image, category
    """
    if not current_products:
        return

    now = datetime.now(timezone.utc).isoformat()
    
    with get_connection() as conn:
        c = conn.cursor()
        
        # 1. Record appearances
        appearances_added = 0
        for p in current_products:
            pid = str(p.get("id", ""))
            if not pid:
                continue
            
            sale_type = p.get("type", "unknown")
            try:
                price = float(p.get("currentPrice", 0) or 0)
            except (ValueError, TypeError):
                price = 0
            try:
                old_price = float(p.get("oldPrice", 0) or 0)
            except (ValueError, TypeError):
                old_price = 0
            discount = calc_discount(price, old_price)

            try:
                c.execute("""
                    INSERT INTO sale_appearances (product_id, sale_type, price, old_price, discount_pct, seen_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (pid, sale_type, price, old_price, discount, now))
                appearances_added += 1
            except sqlite3.IntegrityError:
                pass  # Duplicate (same product_id + seen_at)

        # 2. Update sessions
        current_ids = {str(p.get("id", "")) for p in current_products if p.get("id")}
        
        # Close sessions for products no longer on sale
        c.execute("SELECT id, product_id, first_seen FROM sale_sessions WHERE is_active = 1")
        active_sessions = c.fetchall()
        
        sessions_closed = 0
        for row in active_sessions:
            if row["product_id"] not in current_ids:
                # Product gone — close session
                first = datetime.fromisoformat(row["first_seen"])
                now_dt = datetime.fromisoformat(now)
                duration = int((now_dt - first).total_seconds() / 60)
                c.execute("""
                    UPDATE sale_sessions 
                    SET is_active = 0, last_seen = ?, duration_minutes = ?
                    WHERE id = ?
                """, (now, duration, row["id"]))
                sessions_closed += 1

        # Open/extend sessions for active products
        sessions_opened = 0
        sessions_extended = 0
        for p in current_products:
            pid = str(p.get("id", ""))
            if not pid:
                continue
            
            sale_type = p.get("type", "unknown")
            try:
                price = float(p.get("currentPrice", 0) or 0)
            except (ValueError, TypeError):
                price = 0
            try:
                old_price = float(p.get("oldPrice", 0) or 0)
            except (ValueError, TypeError):
                old_price = 0
            discount = calc_discount(price, old_price)

            # Check for active session
            c.execute("""
                SELECT id, first_seen FROM sale_sessions 
                WHERE product_id = ? AND is_active = 1
            """, (pid,))
            existing = c.fetchone()

            if existing:
                # Extend session
                first = datetime.fromisoformat(existing["first_seen"])
                now_dt = datetime.fromisoformat(now)
                duration = int((now_dt - first).total_seconds() / 60)
                c.execute("""
                    UPDATE sale_sessions 
                    SET last_seen = ?, duration_minutes = ?, price = ?, old_price = ?, discount_pct = ?
                    WHERE id = ?
                """, (now, duration, price, old_price, discount, existing["id"]))
                sessions_extended += 1
            else:
                # New session
                c.execute("""
                    INSERT INTO sale_sessions 
                    (product_id, sale_type, price, old_price, discount_pct, first_seen, last_seen, duration_minutes, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0, 1)
                """, (pid, sale_type, price, old_price, discount, now, now))
                sessions_opened += 1

        # 3. Update product catalog with latest info
        for p in current_products:
            pid = str(p.get("id", ""))
            if not pid:
                continue
            
            name = p.get("name", "")
            category = p.get("category", "")
            image = p.get("image", "")
            sale_type = p.get("type", "unknown")
            try:
                price = float(p.get("currentPrice", 0) or 0)
            except (ValueError, TypeError):
                price = 0

            c.execute("""
                INSERT INTO product_catalog (product_id, name, category, image_url, last_known_price, last_sale_at, last_sale_type, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(product_id) DO UPDATE SET
                    name = excluded.name,
                    category = CASE WHEN excluded.category != '' THEN excluded.category ELSE product_catalog.category END,
                    image_url = CASE WHEN excluded.image_url != '' THEN excluded.image_url ELSE product_catalog.image_url END,
                    last_known_price = excluded.last_known_price,
                    last_sale_at = excluded.last_sale_at,
                    last_sale_type = excluded.last_sale_type,
                    updated_at = excluded.updated_at
            """, (pid, name, category, image, price, now, sale_type, now))

        print(f"📊 Sale history: +{appearances_added} appearances, "
              f"{sessions_opened} opened, {sessions_extended} extended, {sessions_closed} closed")


def update_product_stats():
    """Recalculate stats for all products that have sessions."""
    with get_connection() as conn:
        c = conn.cursor()
        
        # Get all products with at least one session
        c.execute("""
            SELECT DISTINCT product_id FROM sale_sessions
        """)
        product_ids = [row["product_id"] for row in c.fetchall()]
        
        updated = 0
        for pid in product_ids:
            c.execute("""
                SELECT COUNT(*) as cnt,
                       MAX(last_seen) as last_sale,
                       AVG(discount_pct) as avg_disc,
                       MAX(discount_pct) as max_disc,
                       AVG(duration_minutes) as avg_window
                FROM sale_sessions
                WHERE product_id = ?
            """, (pid,))
            stats = c.fetchone()
            
            if stats and stats["cnt"] > 0:
                # Find most common sale time (hour:minute)
                c.execute("""
                    SELECT substr(first_seen, 12, 5) as sale_time, COUNT(*) as cnt
                    FROM sale_sessions
                    WHERE product_id = ?
                    GROUP BY sale_time
                    ORDER BY cnt DESC
                    LIMIT 1
                """, (pid,))
                time_row = c.fetchone()
                usual_time = time_row["sale_time"] if time_row else None
                
                c.execute("""
                    UPDATE product_catalog SET
                        total_sale_count = ?,
                        last_sale_at = ?,
                        avg_discount_pct = ROUND(?, 1),
                        max_discount_pct = ?,
                        usual_sale_time = ?,
                        avg_catch_window_min = ROUND(?, 1),
                        updated_at = ?
                    WHERE product_id = ?
                """, (
                    stats["cnt"],
                    stats["last_sale"],
                    stats["avg_disc"] or 0,
                    stats["max_disc"] or 0,
                    usual_time,
                    stats["avg_window"] or 0,
                    datetime.now(timezone.utc).isoformat(),
                    pid
                ))
                updated += 1
        
        print(f"📈 Updated stats for {updated} products")


def seed_product_catalog():
    """
    Seed product_catalog from category_db.json.
    Only inserts products not already in catalog.
    """
    catdb_path = os.path.join(config.DATA_DIR, "category_db.json")
    if not os.path.exists(catdb_path):
        print(f"❌ category_db.json not found at {catdb_path}")
        return 0

    with open(catdb_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    products = data.get("products", {})
    if not isinstance(products, dict):
        print("❌ category_db.json 'products' is not a dict")
        return 0

    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    
    with get_connection() as conn:
        c = conn.cursor()
        for pid, info in products.items():
            name = info.get("name", "")
            category = info.get("category", "")
            if not name:
                continue
            try:
                c.execute("""
                    INSERT INTO product_catalog (product_id, name, category, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(product_id) DO UPDATE SET
                        category = CASE WHEN excluded.category != '' AND product_catalog.category IS NULL 
                                        THEN excluded.category ELSE product_catalog.category END
                """, (str(pid), name, category, now))
                inserted += 1
            except sqlite3.IntegrityError:
                pass

    print(f"🌱 Seeded {inserted} products into catalog (from {len(products)} in category_db)")
    return inserted


if __name__ == "__main__":
    print("=" * 50)
    print("Sale History — Init & Seed")
    print("=" * 50)
    init_sale_history_tables()
    seed_product_catalog()
    print("\n✅ Done!")

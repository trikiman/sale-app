"""
Database operations for VkusVill Sale Monitor
Uses SQLite for simplicity and portability
"""
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Set
from contextlib import contextmanager

import config
from database.models import User, FavoriteCategory, FavoriteProduct


class Database:
    """SQLite database manager"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DATABASE_PATH
        self._ensure_directory()
        self._init_tables()
        self._init_sale_history_tables()
    
    def _ensure_directory(self):
        """Ensure database directory exists"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
    
    @contextmanager
    def get_connection(self):
        """Get database connection with context manager"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def _init_tables(self):
        """Initialize database tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Favorite categories table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS favorite_categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    category_key TEXT NOT NULL,
                    category_name TEXT NOT NULL,
                    added_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(telegram_id),
                    UNIQUE(user_id, category_key)
                )
            """)
            
            # Favorite products table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS favorite_products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    product_id TEXT NOT NULL,
                    product_name TEXT NOT NULL,
                    added_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(telegram_id),
                    UNIQUE(user_id, product_id)
                )
            """)
            
            # Seen products table (for detecting new items)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS seen_products (
                    product_id TEXT PRIMARY KEY,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    notified INTEGER DEFAULT 0
                )
            """)
            
            # Notification history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notification_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    product_id TEXT NOT NULL,
                    sent_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(telegram_id)
                )
            """)
            
            # Create indices for faster queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_favorite_categories_user 
                ON favorite_categories(user_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_favorite_products_user 
                ON favorite_products(user_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_notification_history_user_product 
                ON notification_history(user_id, product_id)
            """)
            
            # Link tokens table (for Telegram account linking)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS link_tokens (
                    token TEXT PRIMARY KEY,
                    guest_id TEXT NOT NULL,
                    telegram_id INTEGER,
                    created_at TEXT NOT NULL,
                    used INTEGER DEFAULT 0
                )
            """)
    
    def _init_sale_history_tables(self):
        """Initialize sale history tables (Phase 13: HIST-01, HIST-02, HIST-03)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
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
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_appearances_product ON sale_appearances(product_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_appearances_seen ON sale_appearances(seen_at)")
            
            cursor.execute("""
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
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_product ON sale_sessions(product_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_active ON sale_sessions(is_active)")
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS product_catalog (
                    product_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    category TEXT,
                    group_name TEXT,
                    subgroup TEXT,
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
            
            # Migration: add group_name and subgroup columns to existing DBs
            for col in ['group_name TEXT', 'subgroup TEXT']:
                try:
                    cursor.execute(f"ALTER TABLE product_catalog ADD COLUMN {col}")
                except Exception:
                    pass  # Column already exists
            
            # Indices for group/subgroup filtering
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_catalog_group ON product_catalog(group_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_catalog_subgroup ON product_catalog(subgroup)")
    
    # User operations
    
    def upsert_user(self, telegram_id: int, username: str = None, first_name: str = None) -> User:
        """Create or update a user"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            
            cursor.execute("""
                INSERT INTO users (telegram_id, username, first_name, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name
            """, (telegram_id, username, first_name, now))
            
            cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            row = cursor.fetchone()
            return User.from_row(tuple(row))
    
    def get_user(self, telegram_id: int) -> Optional[User]:
        """Get a user by Telegram ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            row = cursor.fetchone()
            return User.from_row(tuple(row)) if row else None
    
    def get_all_users(self) -> List[User]:
        """Get all registered users"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
            return [User.from_row(tuple(row)) for row in cursor.fetchall()]
    
    # Favorite categories operations
    
    def add_favorite_category(self, user_id: int, category_key: str, category_name: str) -> bool:
        """Add a favorite category for a user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now(timezone.utc).isoformat()
                
                cursor.execute("""
                    INSERT INTO favorite_categories (user_id, category_key, category_name, added_at)
                    VALUES (?, ?, ?, ?)
                """, (user_id, category_key, category_name, now))
                
                return True
        except sqlite3.IntegrityError:
            return False  # Already exists
    
    def remove_favorite_category(self, user_id: int, category_key: str) -> bool:
        """Remove a favorite category"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM favorite_categories 
                WHERE user_id = ? AND category_key = ?
            """, (user_id, category_key))
            return cursor.rowcount > 0
    
    def get_user_favorite_categories(self, user_id: int) -> List[FavoriteCategory]:
        """Get all favorite categories for a user"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM favorite_categories WHERE user_id = ?
            """, (user_id,))
            return [FavoriteCategory.from_row(tuple(row)) for row in cursor.fetchall()]
    
    # Favorite products operations
    
    def add_favorite_product(self, user_id: int, product_id: str, product_name: str) -> bool:
        """Add a favorite product for a user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now(timezone.utc).isoformat()
                
                cursor.execute("""
                    INSERT INTO favorite_products (user_id, product_id, product_name, added_at)
                    VALUES (?, ?, ?, ?)
                """, (user_id, product_id, product_name, now))
                
                return True
        except sqlite3.IntegrityError:
            return False  # Already exists
    
    def remove_favorite_product(self, user_id: int, product_id: str) -> bool:
        """Remove a favorite product"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM favorite_products 
                WHERE user_id = ? AND product_id = ?
            """, (user_id, product_id))
            return cursor.rowcount > 0
    
    def get_user_favorite_products(self, user_id: int) -> List[FavoriteProduct]:
        """Get all favorite products for a user"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM favorite_products WHERE user_id = ?
            """, (user_id,))
            return [FavoriteProduct.from_row(tuple(row)) for row in cursor.fetchall()]
    
    # Seen products operations
    
    def mark_product_seen(self, product_id: str) -> bool:
        """Mark a product as seen. Returns True if this is a new product."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            
            # Check if product exists
            cursor.execute("SELECT * FROM seen_products WHERE product_id = ?", (product_id,))
            existing = cursor.fetchone()
            
            if existing:
                # Update last_seen
                cursor.execute("""
                    UPDATE seen_products SET last_seen = ? WHERE product_id = ?
                """, (now, product_id))
                return False  # Not new
            else:
                # Insert new product
                cursor.execute("""
                    INSERT INTO seen_products (product_id, first_seen, last_seen, notified)
                    VALUES (?, ?, ?, 0)
                """, (product_id, now, now))
                return True  # New product
    
    def get_new_products(self, product_ids: List[str]) -> Set[str]:
        """Get which products from the list are new (not seen before)"""
        if not product_ids:
            return set()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ','.join('?' * len(product_ids))
            cursor.execute(f"""
                SELECT product_id FROM seen_products 
                WHERE product_id IN ({placeholders})
            """, product_ids)
            
            seen = {row[0] for row in cursor.fetchall()}
            return set(product_ids) - seen
    
    def mark_products_notified(self, product_ids: List[str]):
        """Mark products as notified"""
        if not product_ids:
            return
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ','.join('?' * len(product_ids))
            cursor.execute(f"""
                UPDATE seen_products SET notified = 1
                WHERE product_id IN ({placeholders})
            """, product_ids)
    
    # Notification history operations
    
    def was_notification_sent(self, user_id: int, product_id: str, hours: int = 24) -> bool:
        """Check if notification was already sent to user for this product recently"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
            
            cursor.execute("""
                SELECT 1 FROM notification_history 
                WHERE user_id = ? AND product_id = ? AND sent_at > ?
            """, (user_id, product_id, cutoff))
            
            return cursor.fetchone() is not None
    
    def record_notification(self, user_id: int, product_id: str):
        """Record that a notification was sent"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            
            cursor.execute("""
                INSERT INTO notification_history (user_id, product_id, sent_at)
                VALUES (?, ?, ?)
            """, (user_id, product_id, now))
    
    # Account linking operations
    
    def store_link_token(self, guest_id: str) -> str:
        """Generate and store a link token for a guest user. Invalidates old tokens."""
        token = secrets.token_urlsafe(16)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            # Invalidate old tokens for this guest
            cursor.execute("DELETE FROM link_tokens WHERE guest_id = ?", (guest_id,))
            cursor.execute("""
                INSERT INTO link_tokens (token, guest_id, created_at)
                VALUES (?, ?, ?)
            """, (token, guest_id, now))
        return token
    
    def get_guest_for_token(self, token: str) -> Optional[str]:
        """Look up guest_id for a link token. Returns None if expired (1hr) or used."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
            cursor.execute("""
                SELECT guest_id FROM link_tokens 
                WHERE token = ? AND used = 0 AND created_at > ?
            """, (token, cutoff))
            row = cursor.fetchone()
            return row[0] if row else None
    
    def migrate_user_data(self, from_id, to_id: int) -> dict:
        """Migrate all favorites/data from one user ID to another. Returns counts."""
        counts = {'products': 0, 'categories': 0, 'notifications': 0}
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Migrate favorite products (skip duplicates)
            cursor.execute("""
                SELECT product_id, product_name, added_at 
                FROM favorite_products WHERE user_id = ?
            """, (from_id,))
            for row in cursor.fetchall():
                try:
                    cursor.execute("""
                        INSERT INTO favorite_products (user_id, product_id, product_name, added_at)
                        VALUES (?, ?, ?, ?)
                    """, (to_id, row[0], row[1], row[2]))
                    counts['products'] += 1
                except sqlite3.IntegrityError:
                    pass  # Already exists for target user
            
            # Migrate favorite categories (skip duplicates)
            cursor.execute("""
                SELECT category_key, category_name, added_at 
                FROM favorite_categories WHERE user_id = ?
            """, (from_id,))
            for row in cursor.fetchall():
                try:
                    cursor.execute("""
                        INSERT INTO favorite_categories (user_id, category_key, category_name, added_at)
                        VALUES (?, ?, ?, ?)
                    """, (to_id, row[0], row[1], row[2]))
                    counts['categories'] += 1
                except sqlite3.IntegrityError:
                    pass
            
            # Clean up old guest data
            cursor.execute("DELETE FROM favorite_products WHERE user_id = ?", (from_id,))
            cursor.execute("DELETE FROM favorite_categories WHERE user_id = ?", (from_id,))
            cursor.execute("DELETE FROM notification_history WHERE user_id = ?", (from_id,))
        
        return counts
    
    def delete_link_token(self, token: str, telegram_id: int):
        """Mark a link token as used and store the linked Telegram ID."""
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE link_tokens SET used = 1, telegram_id = ? WHERE token = ?",
                (telegram_id, token)
            )
    
    def get_linked_telegram_id(self, guest_id: str) -> Optional[int]:
        """Check if a guest ID has been linked to a Telegram ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT telegram_id FROM link_tokens
                WHERE guest_id = ? AND used = 1 AND telegram_id IS NOT NULL
                ORDER BY created_at DESC LIMIT 1
            """, (guest_id,))
            row = cursor.fetchone()
            return row[0] if row else None
    
    def cleanup_old_data(self, days: int = 7):
        """Clean up old seen products and notification history"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            
            # Remove old notification history
            cursor.execute("""
                DELETE FROM notification_history WHERE sent_at < ?
            """, (cutoff,))
            
            # Remove old seen products that haven't been seen recently
            cursor.execute("""
                DELETE FROM seen_products WHERE last_seen < ?
            """, (cutoff,))


# Global database instance
_db_instance: Optional[Database] = None


def get_database() -> Database:
    """Get or create the global database instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance

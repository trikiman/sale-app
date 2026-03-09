"""
Database operations for VkusVill Sale Monitor
Uses SQLite for simplicity and portability
"""
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Set
from contextlib import contextmanager

import config
from database.models import User, FavoriteCategory, FavoriteProduct, SeenProduct


class Database:
    """SQLite database manager"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DATABASE_PATH
        self._ensure_directory()
        self._init_tables()
    
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

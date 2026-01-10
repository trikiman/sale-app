"""
Database models for VkusVill Sale Monitor
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class User:
    """Telegram user"""
    telegram_id: int
    username: Optional[str]
    first_name: Optional[str]
    created_at: datetime
    
    @staticmethod
    def from_row(row: tuple) -> 'User':
        return User(
            telegram_id=row[0],
            username=row[1],
            first_name=row[2],
            created_at=datetime.fromisoformat(row[3]) if isinstance(row[3], str) else row[3]
        )


@dataclass
class FavoriteCategory:
    """User's favorite category"""
    id: int
    user_id: int
    category_key: str
    category_name: str
    added_at: datetime
    
    @staticmethod
    def from_row(row: tuple) -> 'FavoriteCategory':
        return FavoriteCategory(
            id=row[0],
            user_id=row[1],
            category_key=row[2],
            category_name=row[3],
            added_at=datetime.fromisoformat(row[4]) if isinstance(row[4], str) else row[4]
        )


@dataclass
class FavoriteProduct:
    """User's favorite product"""
    id: int
    user_id: int
    product_id: str
    product_name: str
    added_at: datetime
    
    @staticmethod
    def from_row(row: tuple) -> 'FavoriteProduct':
        return FavoriteProduct(
            id=row[0],
            user_id=row[1],
            product_id=row[2],
            product_name=row[3],
            added_at=datetime.fromisoformat(row[4]) if isinstance(row[4], str) else row[4]
        )


@dataclass
class SeenProduct:
    """Tracks products we've seen to detect new ones"""
    product_id: str
    first_seen: datetime
    last_seen: datetime
    notified: bool
    
    @staticmethod
    def from_row(row: tuple) -> 'SeenProduct':
        return SeenProduct(
            product_id=row[0],
            first_seen=datetime.fromisoformat(row[1]) if isinstance(row[1], str) else row[1],
            last_seen=datetime.fromisoformat(row[2]) if isinstance(row[2], str) else row[2],
            notified=bool(row[3])
        )


@dataclass
class NotificationHistory:
    """Tracks sent notifications to avoid duplicates"""
    id: int
    user_id: int
    product_id: str
    sent_at: datetime
    
    @staticmethod
    def from_row(row: tuple) -> 'NotificationHistory':
        return NotificationHistory(
            id=row[0],
            user_id=row[1],
            product_id=row[2],
            sent_at=datetime.fromisoformat(row[3]) if isinstance(row[3], str) else row[3]
        )

"""
Notification System for VkusVill App
Sends Telegram notifications when new products appear or favorites are in stock
"""
import json
import os
import sys
import asyncio
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import Database

# Try to import telegram bot (optional)
try:
    from telegram import Bot
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("Warning: python-telegram-bot not installed. Notifications disabled.")


class Notifier:
    """Handles product notifications"""
    
    def __init__(self, bot_token: str = None):
        self.db = Database()
        self.bot_token = bot_token or os.environ.get('TELEGRAM_BOT_TOKEN')
        self.bot = Bot(self.bot_token) if TELEGRAM_AVAILABLE and self.bot_token else None
        
        # Data paths
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        self.proposals_path = os.path.join(self.data_dir, "proposals.json")
    
    def load_products(self) -> list:
        """Load current products from JSON"""
        if not os.path.exists(self.proposals_path):
            return []
        
        with open(self.proposals_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return data.get('products', [])
    
    def detect_new_products(self) -> list:
        """Detect new products that haven't been seen before"""
        products = self.load_products()
        if not products:
            return []
        
        product_ids = [p['id'] for p in products]
        new_ids = self.db.get_new_products(product_ids)
        
        # Mark all products as seen
        for product in products:
            self.db.mark_product_seen(product['id'])
        
        # Return only new products
        return [p for p in products if p['id'] in new_ids]
    
    def get_favorite_alerts(self) -> dict:
        """Check if any user's favorites are now available"""
        products = self.load_products()
        product_ids = {p['id']: p for p in products}
        
        alerts = {}  # user_id -> [products]
        
        # Get all users
        users = self.db.get_all_users()
        
        for user in users:
            user_favorites = self.db.get_user_favorite_products(user.telegram_id)
            
            for fav in user_favorites:
                if fav.product_id in product_ids:
                    product = product_ids[fav.product_id]
                    
                    # Only notify if not already notified recently
                    if not self.db.was_notification_sent(user.telegram_id, fav.product_id, hours=24):
                        if user.telegram_id not in alerts:
                            alerts[user.telegram_id] = []
                        alerts[user.telegram_id].append(product)
        
        return alerts
    
    def format_product_message(self, product: dict) -> str:
        """Format a product for Telegram message"""
        type_emoji = {'green': '🟢', 'red': '🔴', 'yellow': '🟡'}.get(product['type'], '🏷️')
        discount = round((1 - float(product['currentPrice']) / float(product['oldPrice'])) * 100) if product['oldPrice'] else 0
        
        return (
            f"{type_emoji} *{product['name']}*\n"
            f"💰 {product['currentPrice']}₽ ~~{product['oldPrice']}₽~~ (-{discount}%)\n"
            f"📦 В наличии: {product['stock']} {product['unit']}\n"
            f"[Открыть товар]({product['url']})"
        )
    
    async def send_telegram_message(self, chat_id: int, message: str):
        """Send a message via Telegram"""
        if not self.bot:
            print(f"[DRY RUN] Would send to {chat_id}: {message[:100]}...")
            return
        
        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
        except Exception as e:
            print(f"Failed to send message to {chat_id}: {e}")
    
    async def notify_new_products(self, admin_chat_id: int = None):
        """Notify admin about new products"""
        new_products = self.detect_new_products()
        
        if not new_products:
            print("No new products detected.")
            return 0
        
        print(f"Found {len(new_products)} new products!")
        
        if admin_chat_id:
            # Group by type
            by_type = {'green': [], 'red': [], 'yellow': []}
            for p in new_products:
                by_type.get(p['type'], []).append(p)
            
            message = f"🆕 *Новые товары!* ({len(new_products)} шт.)\n\n"
            
            for type_name, products in by_type.items():
                if products:
                    type_emoji = {'green': '🟢', 'red': '🔴', 'yellow': '🟡'}[type_name]
                    message += f"{type_emoji} {type_name.upper()}: {len(products)} товаров\n"
            
            message += "\n" + "\n\n".join([self.format_product_message(p) for p in new_products[:5]])
            
            if len(new_products) > 5:
                message += f"\n\n...и ещё {len(new_products) - 5} товаров"
            
            await self.send_telegram_message(admin_chat_id, message)
        
        return len(new_products)
    
    async def notify_favorites(self):
        """Notify users about their favorites being available"""
        alerts = self.get_favorite_alerts()
        
        if not alerts:
            print("No favorite alerts to send.")
            return 0
        
        total_sent = 0
        
        for user_id, products in alerts.items():
            message = f"❤️ *Ваши избранные товары в наличии!*\n\n"
            message += "\n\n".join([self.format_product_message(p) for p in products])
            
            await self.send_telegram_message(user_id, message)
            
            # Record notifications
            for product in products:
                self.db.record_notification(user_id, product['id'])
            
            total_sent += len(products)
        
        print(f"Sent {total_sent} favorite alerts to {len(alerts)} users.")
        return total_sent
    
    async def run_notification_cycle(self, admin_chat_id: int = None):
        """Run a full notification cycle"""
        print(f"[{datetime.now().isoformat()}] Running notification cycle...")
        
        # Notify admin about new products
        new_count = await self.notify_new_products(admin_chat_id)
        
        # Notify users about favorites
        fav_count = await self.notify_favorites()
        
        # Cleanup old data
        self.db.cleanup_old_data(days=7)
        
        print(f"Cycle complete: {new_count} new products, {fav_count} favorite alerts")
        return new_count, fav_count


def main():
    """Main entry point for notification script"""
    import argparse
    
    parser = argparse.ArgumentParser(description='VkusVill Notification System')
    parser.add_argument('--admin', type=int, help='Admin Telegram chat ID for new product alerts')
    parser.add_argument('--dry-run', action='store_true', help='Run without sending actual messages')
    args = parser.parse_args()
    
    if args.dry_run:
        print("DRY RUN MODE - No messages will be sent")
    
    notifier = Notifier()
    asyncio.run(notifier.run_notification_cycle(admin_chat_id=args.admin))


if __name__ == "__main__":
    main()

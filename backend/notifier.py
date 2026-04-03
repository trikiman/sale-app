"""
Notification System for VkusVill App
Sends Telegram notifications when new products appear or favorites are in stock
"""
import json
import os
import sys
import asyncio
import logging
from collections import defaultdict
from typing import Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env if available
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))
except ImportError:
    pass

logger = logging.getLogger(__name__)

from database.db import Database

# Try to import telegram bot (optional)
try:
    from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("Warning: python-telegram-bot not installed. Notifications disabled.")


class Notifier:
    """Handles product notifications"""
    
    def __init__(self, bot_token: str = None):
        self.db = Database()
        self.bot_token = bot_token or os.environ.get('TELEGRAM_TOKEN') or os.environ.get('TELEGRAM_BOT_TOKEN')
        
        # Configure proxy for Telegram API (required on networks that block api.telegram.org)
        self.bot = None
        if TELEGRAM_AVAILABLE and self.bot_token:
            proxy_url = os.environ.get('SOCKS5_PROXY', '')
            try:
                if proxy_url:
                    from telegram.request import HTTPXRequest
                    request = HTTPXRequest(proxy=proxy_url, connect_timeout=10, read_timeout=15)
                    self.bot = Bot(self.bot_token, request=request)
                else:
                    self.bot = Bot(self.bot_token)
            except Exception as e:
                logger.warning(f"Failed to init Bot{f' with proxy ({proxy_url})' if proxy_url else ''}: {e}")
                # Fallback: try without proxy
                try:
                    self.bot = Bot(self.bot_token)
                except Exception:
                    pass
        
        # Data paths
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        self.proposals_path = os.path.join(self.data_dir, "proposals.json")
        
        if not self.bot:
            logger.warning("Telegram bot not initialized — notifications will be dry-run only")

    def _normalize_category_value(self, value: Optional[str]) -> str:
        """Normalize whitespace without changing the meaning of the category name."""
        if not value:
            return ""
        return " ".join(str(value).replace('\xa0', ' ').split())

    def _enrich_product_categories(self, products: list) -> list:
        """Fill group/subgroup from product_catalog when proposals.json lacks them."""
        metadata_by_id = self.db.get_product_catalog_metadata([p.get('id') for p in products if p.get('id')])
        enriched = []

        for raw_product in products:
            product = dict(raw_product)
            meta = metadata_by_id.get(str(product.get('id')), {})
            group = (
                product.get('group')
                or meta.get('group')
                or product.get('category')
                or meta.get('category')
                or ''
            )
            subgroup = product.get('subgroup') or meta.get('subgroup') or ''
            product['group'] = self._normalize_category_value(group)
            product['subgroup'] = self._normalize_category_value(subgroup)
            enriched.append(product)

        return enriched

    def _parse_category_key(self, category_key: str) -> Optional[dict]:
        """Parse favorite category keys from the existing group:X / subgroup:X/Y format."""
        if not category_key:
            return None

        if category_key.startswith('group:'):
            group = self._normalize_category_value(category_key.split(':', 1)[1])
            if not group:
                return None
            return {"kind": "group", "group": group}

        if category_key.startswith('subgroup:'):
            value = category_key.split(':', 1)[1]
            if '/' not in value:
                return None
            group, subgroup = value.split('/', 1)
            group = self._normalize_category_value(group)
            subgroup = self._normalize_category_value(subgroup)
            if not group or not subgroup:
                return None
            return {"kind": "subgroup", "group": group, "subgroup": subgroup}

        return None

    def _build_match_reason(self, kind: str, group: str = '', subgroup: str = '') -> dict:
        if kind == 'subgroup':
            return {
                "kind": "subgroup",
                "priority": 3,
                "text": f"🎯 Подгруппа: {group} -> {subgroup}",
            }
        if kind == 'group':
            return {
                "kind": "group",
                "priority": 2,
                "text": f"🎯 Категория: {group}",
            }
        return {
            "kind": "product",
            "priority": 1,
            "text": "❤️ Товар у вас в избранном",
        }

    def _select_primary_reason(self, reasons: list) -> Optional[dict]:
        if not reasons:
            return None
        return max(reasons, key=lambda reason: reason["priority"])
    
    def load_products(self) -> list:
        """Load current products from JSON"""
        if not os.path.exists(self.proposals_path):
            return []
        
        with open(self.proposals_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return data.get('products', [])
    
    def detect_new_products(self) -> list:
        """Detect new products that haven't been seen before.
        
        NOTE (BOT-04): Does NOT mark products as seen — caller must call
        mark_all_products_seen() after all per-user notifications are sent.
        """
        products = self.load_products()
        if not products:
            return []
        
        product_ids = [p['id'] for p in products]
        new_ids = self.db.get_new_products(product_ids)
        
        # Return only new products (don't mark as seen yet — BOT-04 fix)
        return [p for p in products if p['id'] in new_ids]
    
    def mark_all_products_seen(self):
        """Mark all current products as seen. Call AFTER all notifications."""
        products = self.load_products()
        for product in products:
            self.db.mark_product_seen(product['id'])
    
    def get_favorite_alerts(self) -> dict:
        """Check if any user's favorites are now available"""
        products = self._enrich_product_categories(self.load_products())
        products_by_id = {str(p['id']): p for p in products if p.get('id')}
        products_by_group = defaultdict(list)
        products_by_subgroup = defaultdict(list)

        for product in products:
            group = self._normalize_category_value(product.get('group') or product.get('category'))
            subgroup = self._normalize_category_value(product.get('subgroup'))
            if group:
                products_by_group[group].append(product)
                if subgroup:
                    products_by_subgroup[(group, subgroup)].append(product)
        
        alerts = {}  # user_id -> [{product, reasons, match_reason}]
        
        # Get all users
        users = self.db.get_all_users()
        
        for user in users:
            user_alerts = {}
            user_favorites = self.db.get_user_favorite_products(user.telegram_id)
            
            for fav in user_favorites:
                product_id = str(fav.product_id)
                product = products_by_id.get(product_id)
                if not product:
                    continue
                if self.db.was_notification_sent(user.telegram_id, product_id, hours=24):
                    continue

                entry = user_alerts.setdefault(product_id, {"product": product, "reasons": []})
                if not any(reason["kind"] == "product" for reason in entry["reasons"]):
                    entry["reasons"].append(self._build_match_reason("product"))

            category_favorites = self.db.get_user_favorite_categories(user.telegram_id)
            for favorite in category_favorites:
                parsed = self._parse_category_key(favorite.category_key)
                if not parsed:
                    continue

                if parsed["kind"] == "group":
                    matched_products = products_by_group.get(parsed["group"], [])
                    reason = self._build_match_reason("group", group=parsed["group"])
                else:
                    matched_products = products_by_subgroup.get((parsed["group"], parsed["subgroup"]), [])
                    reason = self._build_match_reason(
                        "subgroup",
                        group=parsed["group"],
                        subgroup=parsed["subgroup"],
                    )

                for product in matched_products:
                    product_id = str(product.get('id'))
                    if self.db.was_notification_sent(user.telegram_id, product_id, hours=24):
                        continue

                    entry = user_alerts.setdefault(product_id, {"product": product, "reasons": []})
                    if not any(existing["text"] == reason["text"] for existing in entry["reasons"]):
                        entry["reasons"].append(reason)

            if user_alerts:
                compiled = []
                for product_id, entry in user_alerts.items():
                    entry["match_reason"] = self._select_primary_reason(entry["reasons"])
                    compiled.append(entry)
                alerts[user.telegram_id] = compiled
        
        return alerts
    
    def format_product_message(self, product: dict, reason_text: Optional[str] = None) -> str:
        """Format a product for Telegram message"""
        type_emoji = {'green': '🟢', 'red': '🔴', 'yellow': '🟡'}.get(product['type'], '🏷️')
        discount = round((1 - float(product['currentPrice']) / float(product['oldPrice'])) * 100) if product.get('oldPrice') else 0

        lines = [
            f"{type_emoji} *{product['name']}*\n"
            f"💰 {product['currentPrice']}₽ ~~{product.get('oldPrice','')}₽~~ (-{discount}%)\n"
            f"📦 В наличии: {product.get('stock','?')} {product.get('unit','шт')}"
        ]
        if reason_text:
            lines.append(reason_text)
        return "\n".join(lines)
    
    def get_product_keyboard(self, product: dict):
        """Build inline keyboard buttons for a product notification"""
        buttons = []
        # Open product URL button
        url = product.get('url')
        if url:
            buttons.append(InlineKeyboardButton("🌐 Открыть", url=url))
        # Add to cart callback button
        is_grn = 1 if product.get('type') == 'green' else 0
        price_type = 222 if is_grn else 1
        callback_data = f"cart_add_{product['id']}_{is_grn}_{price_type}"
        buttons.append(InlineKeyboardButton("🛒 В корзину", callback_data=callback_data))
        return InlineKeyboardMarkup([buttons])
    
    async def send_telegram_message(self, chat_id: int, message: str, reply_markup=None):
        """Send a message via Telegram"""
        if not self.bot:
            logger.info(f"[DRY RUN] Would send to {chat_id}: {message[:100]}...")
            return
        
        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode='Markdown',
                disable_web_page_preview=True,
                reply_markup=reply_markup
            )
            logger.info(f"✅ Sent notification to {chat_id}")
        except Exception as e:
            logger.error(f"Failed to send message to {chat_id}: {e}")
    
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
            logger.info("No favorite alerts to send.")
            return 0
        
        total_sent = 0
        
        for user_id, entries in alerts.items():
            # Send header
            header = f"❤️ *Нашлись товары из вашего избранного!* ({len(entries)} шт.)"
            await self.send_telegram_message(user_id, header)
            
            # Send each product with inline buttons (limit 10)
            for entry in entries[:10]:
                product = entry["product"]
                reason_text = (entry.get("match_reason") or {}).get("text")
                msg = self.format_product_message(product, reason_text=reason_text)
                keyboard = self.get_product_keyboard(product)
                await self.send_telegram_message(user_id, msg, reply_markup=keyboard)
                self.db.record_notification(user_id, product['id'])
            
            if len(entries) > 10:
                await self.send_telegram_message(
                    user_id,
                    f"...и ещё {len(entries) - 10} товаров"
                )
            
            total_sent += len(entries)
        
        logger.info(f"Sent {total_sent} favorite alerts to {len(alerts)} users.")
        return total_sent
    
    async def run_notification_cycle(self, admin_chat_id: int = None):
        """Run a full notification cycle"""
        logger.info("Running notification cycle...")
        
        # Notify admin about new products
        new_count = await self.notify_new_products(admin_chat_id)
        
        # Notify users about favorites
        fav_count = await self.notify_favorites()
        
        # NOW mark all products as seen (BOT-04: after all users notified)
        self.mark_all_products_seen()
        
        # Cleanup old data
        self.db.cleanup_old_data(days=7)
        
        logger.info(f"Cycle complete: {new_count} new products, {fav_count} favorite alerts")
        return new_count, fav_count


def main():
    """Main entry point for notification script"""
    import argparse
    
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    
    parser = argparse.ArgumentParser(description='VkusVill Notification System')
    parser.add_argument('--admin', type=int, help='Admin Telegram chat ID for new product alerts')
    parser.add_argument('--dry-run', action='store_true', help='Run without sending actual messages')
    args = parser.parse_args()
    
    # Auto-load admin chat ID from env if not specified
    admin_id = args.admin or os.environ.get('ADMIN_CHAT_ID')
    if admin_id and isinstance(admin_id, str):
        admin_id = int(admin_id)
    
    if args.dry_run:
        logger.info("DRY RUN MODE - No messages will be sent")
    
    notifier = Notifier()
    # python-telegram-bot requires SelectorEventLoop on Windows (ProactorEventLoop causes errors)
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(notifier.run_notification_cycle(admin_chat_id=admin_id))


if __name__ == "__main__":
    main()

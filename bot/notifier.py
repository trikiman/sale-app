"""
Notification system for VkusVill Sale Monitor
Sends Telegram notifications when matching sales are found
"""
import logging
from typing import List, Dict, Set

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.constants import ParseMode
from telegram.error import TelegramError

import config
from database.db import get_database
from scraper.vkusvill import Product


logger = logging.getLogger(__name__)


class Notifier:
    """Handles sending notifications to users"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.db = get_database()
    
    async def notify_user(self, user_id: int, products: List[Product]):
        """Send notifications about products to a specific user"""
        if not products:
            return
        
        # Filter out products we've already notified about
        products_to_notify = []
        for product in products:
            if not self.db.was_notification_sent(user_id, product.id):
                products_to_notify.append(product)
        
        if not products_to_notify:
            logger.debug(f"No new products to notify user {user_id}")
            return
        
        # Send header message
        try:
            header = (
                f"🔔 <b>Новые скидки!</b>\n\n"
                f"Найдено {len(products_to_notify)} новых товаров со скидками "
                f"в твоих избранных категориях:"
            )
            await self.bot.send_message(
                chat_id=user_id,
                text=header,
                parse_mode=ParseMode.HTML
            )
            
            # Send product messages
            for product in products_to_notify[:10]:  # Limit to 10 per notification
                is_grn = 1 if product.is_green_price else 0
                price_type = 222 if product.is_green_price else 1
                callback_data = f"cart_add_{product.id}_{is_grn}_{price_type}"
                keyboard = [[
                    InlineKeyboardButton("🛒 В корзину", callback_data=callback_data),
                    InlineKeyboardButton("🌐 Открыть", web_app=WebAppInfo(url=config.WEB_APP_URL))
                ]]
                
                try:
                    await self.bot.send_message(
                        chat_id=user_id,
                        text=product.formatted_message,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True,
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                    
                    # Record notification
                    self.db.record_notification(user_id, product.id)
                    
                except TelegramError as e:
                    logger.error(f"Failed to send product notification to {user_id}: {e}")
            
            if len(products_to_notify) > 10:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=f"...и ещё {len(products_to_notify) - 10} товаров. "
                         f"Используй /sales для просмотра всех!",
                    parse_mode=ParseMode.HTML
                )
                
            logger.info(f"Notified user {user_id} about {len(products_to_notify)} products")
            
        except TelegramError as e:
            logger.error(f"Failed to notify user {user_id}: {e}")
    
    async def notify_all_users(self, products_by_category: Dict[str, List[Product]]):
        """Notify all users about matching products in their favorite categories"""
        users = self.db.get_all_users()
        
        for user in users:
            try:
                # Get user's favorite categories
                favorites = self.db.get_user_favorite_categories(user.telegram_id)
                
                if not favorites:
                    continue
                
                favorite_keys = {f.category_key for f in favorites}
                
                # Collect matching products
                matching_products: Dict[str, Product] = {}
                
                for category_key in favorite_keys:
                    if category_key in products_by_category:
                        for product in products_by_category[category_key]:
                            if product.id not in matching_products:
                                matching_products[product.id] = product
                
                if matching_products:
                    await self.notify_user(
                        user.telegram_id,
                        list(matching_products.values())
                    )
                    
            except Exception as e:
                logger.error(f"Error notifying user {user.telegram_id}: {e}")
    
    async def notify_new_green_prices(self, products: List[Product]):
        """Notify all users about new green price products in their favorites"""
        if not products:
            return
        
        users = self.db.get_all_users()
        
        for user in users:
            try:
                favorites = self.db.get_user_favorite_categories(user.telegram_id)
                
                if not favorites:
                    continue
                
                # Get favorite category slugs
                favorite_slugs = set()
                for fav in favorites:
                    if fav.category_key in config.CATEGORIES:
                        favorite_slugs.add(config.CATEGORIES[fav.category_key]['slug'])
                        favorite_slugs.add(config.CATEGORIES[fav.category_key]['name'].lower())
                
                # Filter products matching user's favorites
                matching = []
                for product in products:
                    product_category_lower = product.category.lower()
                    
                    for slug in favorite_slugs:
                        # Fuzzy match on category
                        slug_words = slug.replace('-', ' ').split()
                        if any(word in product_category_lower for word in slug_words):
                            matching.append(product)
                            break
                
                if matching:
                    # Check for new products
                    new_product_ids = self.db.get_new_products([p.id for p in matching])
                    new_products = [p for p in matching if p.id in new_product_ids]
                    
                    # Mark as seen
                    for product in matching:
                        self.db.mark_product_seen(product.id)
                    
                    if new_products:
                        await self.notify_user(user.telegram_id, new_products)
                        
            except Exception as e:
                logger.error(f"Error processing user {user.telegram_id}: {e}")


_notifier_instance = None


def get_notifier(bot: Bot = None) -> Notifier:
    """Get or create the notifier instance"""
    global _notifier_instance
    if _notifier_instance is None and bot is not None:
        _notifier_instance = Notifier(bot)
    return _notifier_instance

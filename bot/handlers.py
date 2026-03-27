"""
Telegram Bot Handlers for VkusVill Sale Monitor
"""
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler,
    ContextTypes
)
from telegram.constants import ParseMode

import config
from database.db import get_database
from scraper.vkusvill import get_scraper


# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# Command handlers

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    db = get_database()
    
    # Register user
    db.upsert_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name
    )
    
    # Handle deep link for account linking: /start link_TOKEN
    if context.args and context.args[0].startswith("link_"):
        token = context.args[0][5:]  # Remove "link_" prefix
        guest_id = db.get_guest_for_token(token)
        
        if not guest_id:
            await update.message.reply_text(
                "❌ Ссылка недействительна или истекла.\n"
                "Попробуйте создать новую на сайте.",
                parse_mode=ParseMode.HTML
            )
            return
        
        # Migrate all data from guest to real Telegram user
        counts = db.migrate_user_data(from_id=guest_id, to_id=user.id)
        db.delete_link_token(token, telegram_id=user.id)
        
        total = counts['products'] + counts['categories']
        msg = (
            f"✅ <b>Аккаунт привязан!</b>\n\n"
            f"Привет, {user.first_name}! 👋\n\n"
        )
        if total > 0:
            msg += (
                f"📦 Перенесено: {counts['products']} товаров, "
                f"{counts['categories']} категорий\n\n"
            )
        msg += (
            "🔔 Теперь ты будешь получать уведомления, "
            "когда избранные товары появятся со скидкой!"
        )
        
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
        return
    
    welcome_message = f"""
🛒 <b>Добро пожаловать в VkusVill Sale Monitor!</b>

Привет, {user.first_name}! 👋

Я буду уведомлять тебя о скидках и зелёных ценниках во ВкусВилле.

<b>Что я умею:</b>
• 🟢 Отслеживать зелёные ценники (скидка 40%)
• 📂 Следить за любимыми категориями
• 🔔 Уведомлять о новых скидках каждые 5 минут

<b>Команды:</b>
/categories - Показать все категории
/add - Добавить категорию в избранное
/remove - Убрать категорию из избранного
/favorites - Мои избранные категории
/sales - Текущие зелёные ценники
/check - Проверить скидки сейчас
/help - Помощь

Начни с команды /add, чтобы добавить любимые категории!
"""
    
    await update.message.reply_text(
        welcome_message,
        parse_mode=ParseMode.HTML
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """
<b>📖 Справка по командам</b>

<b>Управление категориями:</b>
/categories - Список всех доступных категорий
/add - Добавить категорию в избранное
/remove - Убрать категорию из избранного
/favorites - Показать мои избранные

<b>Просмотр скидок:</b>
/sales - Показать текущие зелёные ценники
/check - Принудительно проверить скидки

<b>Как это работает:</b>
1. Добавь категории в избранное командой /add
2. Бот будет проверять скидки каждые 5 минут
3. Когда появится товар со скидкой в твоих категориях - получишь уведомление!

<b>Зелёные ценники</b> - это товары со скидкой от 40%, обычно с коротким сроком годности.
"""
    
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)


async def categories_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /categories command - show all available categories"""
    text = "<b>📂 Доступные категории:</b>\n\n"
    
    for key, cat in config.CATEGORIES.items():
        text += f"• <code>{key}</code> - {cat['name']}\n"
    
    text += "\n💡 Используй /add для добавления категории в избранное"
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /add command - show category selection buttons"""
    db = get_database()
    user_id = update.effective_user.id
    
    # Get user's current favorites
    favorites = db.get_user_favorite_categories(user_id)
    favorite_keys = {f.category_key for f in favorites}
    
    # Create keyboard with available categories
    keyboard = []
    row = []
    
    for key, cat in config.CATEGORIES.items():
        if key not in favorite_keys:
            # Use emoji to indicate it's not selected
            btn = InlineKeyboardButton(
                text=f"➕ {cat['name'][:20]}",
                callback_data=f"add_cat:{key}"
            )
            row.append(btn)
            
            if len(row) == 2:
                keyboard.append(row)
                row = []
    
    if row:
        keyboard.append(row)
    
    if not keyboard:
        await update.message.reply_text(
            "✅ Все категории уже добавлены в избранное!",
            parse_mode=ParseMode.HTML
        )
        return
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "<b>➕ Выбери категорию для добавления:</b>",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )


async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /remove command - show favorites for removal"""
    db = get_database()
    user_id = update.effective_user.id
    
    favorites = db.get_user_favorite_categories(user_id)
    
    if not favorites:
        await update.message.reply_text(
            "📭 У тебя пока нет избранных категорий.\nИспользуй /add чтобы добавить!",
            parse_mode=ParseMode.HTML
        )
        return
    
    keyboard = []
    for fav in favorites:
        keyboard.append([
            InlineKeyboardButton(
                text=f"❌ {fav.category_name}",
                callback_data=f"rm_cat:{fav.category_key}"
            )
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "<b>❌ Выбери категорию для удаления:</b>",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )


async def favorites_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /favorites command - show user's favorites"""
    db = get_database()
    user_id = update.effective_user.id
    
    categories = db.get_user_favorite_categories(user_id)
    products = db.get_user_favorite_products(user_id)
    
    text = "<b>⭐ Мои избранные:</b>\n\n"
    
    if categories:
        text += "<b>📂 Категории:</b>\n"
        for cat in categories:
            text += f"  • {cat.category_name}\n"
    else:
        text += "📂 Категории: <i>не выбраны</i>\n"
    
    text += "\n"
    
    if products:
        text += "<b>📦 Товары:</b>\n"
        for prod in products:
            text += f"  • {prod.product_name}\n"
    else:
        text += "📦 Товары: <i>не выбраны</i>\n"
    
    text += "\n💡 Используй /add или /remove для управления избранным"
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def sales_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /sales command - show current green prices"""
    await update.message.reply_text(
        "🔍 Загружаю зелёные ценники...",
        parse_mode=ParseMode.HTML
    )
    
    try:
        scraper = get_scraper()
        products = await scraper.fetch_green_prices_from_cart()
        
        if not products:
            await update.message.reply_text(
                "😔 Зелёные ценники не найдены. Попробуй позже!",
                parse_mode=ParseMode.HTML
            )
            return
        
        # Send first 10 products
        count = min(10, len(products))
        await update.message.reply_text(
            f"🟢 <b>Найдено {len(products)} товаров с зелёными ценниками</b>\n"
            f"Показываю первые {count}:",
            parse_mode=ParseMode.HTML
        )
        
        for product in products[:count]:
            is_grn = 1 if product.is_green_price else 0
            price_type = 222 if product.is_green_price else 1
            callback_data = f"cart_add_{product.id}_{is_grn}_{price_type}"
            keyboard = [[
                InlineKeyboardButton("🛒 В корзину", callback_data=callback_data),
                InlineKeyboardButton("🌐 Открыть", web_app=WebAppInfo(url=config.WEB_APP_URL))
            ]]
            
            await update.message.reply_text(
                product.formatted_message,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        if len(products) > count:
            await update.message.reply_text(
                f"...и ещё {len(products) - count} товаров. "
                "Добавь категории в избранное, чтобы получать только нужные!",
                parse_mode=ParseMode.HTML
            )
            
    except Exception as e:
        logger.error(f"Error fetching sales: {e}")
        await update.message.reply_text(
            "❌ Ошибка при загрузке. Попробуй позже!",
            parse_mode=ParseMode.HTML
        )


async def test_cart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /test_cart command — send a test product card to verify cart button works."""
    test_product_id = 731
    callback_data = f"cart_add_{test_product_id}_0_1"
    keyboard = [[
        InlineKeyboardButton("🛒 В корзину", callback_data=callback_data),
        InlineKeyboardButton("🌐 Открыть", web_app=WebAppInfo(url=config.WEB_APP_URL))
    ]]
    
    text = (
        "🧪 <b>Тестовая карточка товара</b>\n\n"
        "🍌 <b>Бананы</b>\n"
        "💰 Цена: ~165 ₽/кг\n"
        "📦 ID: 731\n\n"
        "Нажми кнопку ниже, чтобы проверить добавление в корзину:"
    )
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /check command - force check for sales in favorites"""
    db = get_database()
    user_id = update.effective_user.id
    
    favorites = db.get_user_favorite_categories(user_id)
    
    if not favorites:
        await update.message.reply_text(
            "📭 У тебя нет избранных категорий.\n"
            "Добавь их через /add чтобы получать уведомления!",
            parse_mode=ParseMode.HTML
        )
        return
    
    await update.message.reply_text(
        f"🔍 Проверяю скидки в {len(favorites)} категориях...",
        parse_mode=ParseMode.HTML
    )
    
    try:
        scraper = get_scraper()
        favorite_keys = [f.category_key for f in favorites]
        
        # Check if logged in
        is_logged = await scraper.is_logged_in()
        if not is_logged:
            await update.message.reply_text(
                "⚠️ Не авторизован во ВкусВилле. Запустите login.py для входа.",
                parse_mode=ParseMode.HTML
            )
            return
        
        # Get green prices
        green_products = await scraper.fetch_green_prices_from_cart()
        
        # Filter green products by favorite categories
        favorite_slugs = {config.CATEGORIES[k]['slug'] for k in favorite_keys if k in config.CATEGORIES}
        favorite_names = {config.CATEGORIES[k]['name'].lower() for k in favorite_keys if k in config.CATEGORIES}
        matching_products = []
        
        for p in green_products:
            # Check if product category matches any favorite
            product_cat_lower = p.category.lower()
            for slug in favorite_slugs:
                slug_words = slug.replace('-', ' ').split()
                if any(word in product_cat_lower for word in slug_words):
                    matching_products.append(p)
                    break
            else:
                # Also check category names
                for name in favorite_names:
                    if any(word in product_cat_lower for word in name.split()[:2]):
                        matching_products.append(p)
                        break
        
        all_products = {p.id: p for p in matching_products}
        
        if not all_products:
            await update.message.reply_text(
                "😔 В избранных категориях сейчас нет скидок.",
                parse_mode=ParseMode.HTML
            )
            return
        
        # Mark as seen
        for product_id in all_products.keys():
            db.mark_product_seen(product_id)
        
        count = min(5, len(all_products))
        await update.message.reply_text(
            f"🎉 <b>Найдено {len(all_products)} товаров со скидками!</b>\n"
            f"Показываю первые {count}:",
            parse_mode=ParseMode.HTML
        )
        
        for product in list(all_products.values())[:count]:
            is_grn = 1 if product.is_green_price else 0
            price_type = 222 if product.is_green_price else 1
            callback_data = f"cart_add_{product.id}_{is_grn}_{price_type}"
            keyboard = [[
                InlineKeyboardButton("🛒 В корзину", callback_data=callback_data),
                InlineKeyboardButton("🌐 Открыть", web_app=WebAppInfo(url=config.WEB_APP_URL))
            ]]
            
            await update.message.reply_text(
                product.formatted_message,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
    except Exception as e:
        logger.error(f"Error checking sales: {e}")
        await update.message.reply_text(
            "❌ Ошибка при проверке. Попробуй позже!",
            parse_mode=ParseMode.HTML
        )


# Callback query handlers

async def handle_add_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle category add button press"""
    query = update.callback_query
    await query.answer()
    
    category_key = query.data.replace("add_cat:", "")
    
    if category_key not in config.CATEGORIES:
        await query.edit_message_text("❌ Категория не найдена")
        return
    
    db = get_database()
    category = config.CATEGORIES[category_key]
    
    success = db.add_favorite_category(
        user_id=update.effective_user.id,
        category_key=category_key,
        category_name=category['name']
    )
    
    if success:
        await query.edit_message_text(
            f"✅ Категория <b>{category['name']}</b> добавлена в избранное!\n\n"
            "Теперь ты будешь получать уведомления о скидках в этой категории.",
            parse_mode=ParseMode.HTML
        )
    else:
        await query.edit_message_text(
            f"ℹ️ Категория <b>{category['name']}</b> уже в избранном.",
            parse_mode=ParseMode.HTML
        )


async def handle_remove_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle category remove button press"""
    query = update.callback_query
    await query.answer()
    
    category_key = query.data.replace("rm_cat:", "")
    
    db = get_database()
    category_name = config.CATEGORIES.get(category_key, {}).get('name', category_key)
    
    success = db.remove_favorite_category(
        user_id=update.effective_user.id,
        category_key=category_key
    )
    
    if success:
        await query.edit_message_text(
            f"✅ Категория <b>{category_name}</b> удалена из избранного.",
            parse_mode=ParseMode.HTML
        )
    else:
        await query.edit_message_text(
            "❌ Не удалось удалить категорию.",
            parse_mode=ParseMode.HTML
        )


async def handle_cart_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle 'Add to Cart' button press via VkusVillCart API"""
    query = update.callback_query
    # Don't answer yet — answer once with the final result (Telegram allows only 1 answer)

    parts = query.data.split('_')
    if len(parts) >= 5:
        product_id = int(parts[2])
        is_green = int(parts[3])
        price_type = int(parts[4])
        user_id = update.effective_user.id

        # Resolve paths dynamically
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cookies_path = os.path.join(base_dir, "data", "user_cookies", f"{user_id}.json")

        cart = None
        try:
            from cart.vkusvill_api import VkusVillCart

            if not os.path.exists(cookies_path):
                await query.answer("❌ Вы не авторизованы! Войдите через веб-приложение.", show_alert=True)
                return

            cart = VkusVillCart(cookies_path=cookies_path)
            result = cart.add(product_id=product_id, price_type=price_type, is_green=is_green)

            if result.get('success'):
                msg = f"✅ Добавлено!\n\nКорзина: {result.get('cart_items', '?')} шт. на {result.get('cart_total', '?')} руб."
                await query.answer(msg, show_alert=True)
            else:
                error = result.get('error', 'Неизвестная ошибка')
                msg = f"❌ Ошибка: {error}"
                await query.answer(msg, show_alert=True)

        except Exception as e:
            logger.error(f"Cart add error: {e}")
            await query.answer("❌ Ошибка при обращении к API", show_alert=True)
        finally:
            if cart:
                cart.close()
    else:
        await query.answer("❌ Ошибка в данных кнопки", show_alert=True)


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route callback queries to appropriate handlers"""
    query = update.callback_query
    data = query.data
    
    if data.startswith("add_cat:"):
        await handle_add_category(update, context)
    elif data.startswith("rm_cat:"):
        await handle_remove_category(update, context)
    elif data.startswith("cart_add_"):
        await handle_cart_add(update, context)
    else:
        await query.answer("Неизвестное действие")


def setup_handlers(application: Application):
    """Set up all bot handlers"""
    from bot.auth import get_login_conv_handler

    # Must add ConversationHandler before simple command handlers that might conflict
    application.add_handler(get_login_conv_handler())

    # Command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("categories", categories_command))
    application.add_handler(CommandHandler("add", add_command))
    application.add_handler(CommandHandler("remove", remove_command))
    application.add_handler(CommandHandler("favorites", favorites_command))
    application.add_handler(CommandHandler("sales", sales_command))
    application.add_handler(CommandHandler("check", check_command))
    application.add_handler(CommandHandler("test_cart", test_cart_command))
    
    # Callback query handler
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    logger.info("Bot handlers registered")

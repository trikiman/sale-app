"""
Telegram Bot Authentication Module for VkusVill
Handles the `/login` command and SMS verification flow via Playwright.
"""
import os
import re
import json
import logging
import asyncio
from typing import Dict, Any, Optional

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from scraper.vkusvill import PlaywrightScraper

logger = logging.getLogger(__name__)

# Define conversation states
PHONE, CODE = range(2)

# Temporary memory to store Playwright scraper instances during login flow
_scrapers: Dict[int, PlaywrightScraper] = {}


def get_user_cookies_path(telegram_id: int) -> str:
    """Returns the absolute path to the user's cookies file."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    user_cookies_dir = os.path.join(base_dir, "data", "user_cookies")
    os.makedirs(user_cookies_dir, exist_ok=True)
    return os.path.join(user_cookies_dir, f"{telegram_id}.json")


def clean_phone_number(phone: str) -> str:
    """Removes all non-digit characters from a phone number."""
    return re.sub(r'\D', '', phone)


async def login_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the login process and asks for a phone number."""
    telegram_id = update.effective_user.id
    context.user_data["_login_telegram_id"] = telegram_id

    await update.message.reply_text(
        "🔐 <b>Авторизация во ВкусВилл</b>\n\n"
        "Чтобы добавлять товары в корзину, мне нужно авторизоваться в вашем профиле.\n\n"
        "Пожалуйста, введите ваш номер телефона в формате <b>+7 900 123 45 67</b>:",
        parse_mode="HTML"
    )
    
    return PHONE


def normalize_phone(phone: str) -> Optional[str]:
    """
    Cleans phone number from spaces/dashes and extracts the 10-digit core.
    Supports +7, 8, 7 prefixes, and raw 10 digits.
    """
    digits = re.sub(r'\D', '', phone)
    
    if len(digits) == 10:
        return digits
    elif len(digits) == 11 and digits.startswith(('7', '8')):
        return digits[1:]
    
    return None

async def receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the received phone number and triggers Playwright to send SMS."""
    telegram_id = update.effective_user.id
    raw_phone = update.message.text.strip()
    
    vkusvill_phone = normalize_phone(raw_phone)
    if not vkusvill_phone:
        await update.message.reply_text(
            "❌ Некорректный формат телефона. Введите 10 цифр (например, +7 900 123 45 67, 89001234567):"
        )
        return PHONE

        
    await update.message.reply_text(
        "⏳ Открываю интерфейс ВкусВилл и отправляю SMS с кодом. "
        "Пожалуйста, подождите пару секунд..."
    )
    
    # Clean up any existing scraper for this user
    if telegram_id in _scrapers:
        await _scrapers[telegram_id].close()
        del _scrapers[telegram_id]
        
    # Start a fresh scraper just for login
    scraper = PlaywrightScraper(cookies_path=get_user_cookies_path(telegram_id))
    try:
        await scraper.initialize()
        
        # In a real scenario, you'd add methods to PlaywrightScraper to handle entering the phone number
        # For now, let's assume we implement `send_sms_code(phone)`
        success = await scraper.send_sms_code(vkusvill_phone)
        
        if success:
            _scrapers[telegram_id] = scraper
            masked_phone = f"+7 {vkusvill_phone[:3]} *** {vkusvill_phone[-2:]}"
            await update.message.reply_text(
                f"✅ SMS отправлено на номер {masked_phone}\n\n"
                f"Введите 6-значный код из сообщения:"
            )
            return CODE
        else:
            await scraper.close()
            await update.message.reply_text(
                "❌ Не удалось отправить SMS. Возможно, номер заблокирован или сайт недоступен.\n"
                "Попробуйте команду /login позже."
            )
            return ConversationHandler.END
            
    except Exception as e:
        logger.error(f"Error during login (phone stage): {e}")
        await scraper.close()
        await update.message.reply_text(
            "❌ Произошла системная ошибка при попытке входа. Попробуйте позже обойдя."
        )
        return ConversationHandler.END


async def receive_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives the SMS code, verifies it with Playwright, and saves cookies."""
    telegram_id = update.effective_user.id
    code = update.message.text.strip()
    
    if not code.isdigit() or len(code) != 6:
        await update.message.reply_text("❌ Введите корректный 6-значный код.")
        return CODE
        
    scraper = _scrapers.get(telegram_id)
    if not scraper:
        await update.message.reply_text("❌ Сессия авторизации истекла. Начните заново с /login.")
        return ConversationHandler.END
        
    await update.message.reply_text("⏳ Проверяю код и сохраняю профиль...")
    
    try:
        # We need to implement `submit_sms_code(code)` in PlaywrightScraper
        success = await scraper.submit_sms_code(code)
        
        if success:
            # Note: submit_sms_code should automatically save cookies to get_user_cookies_path(telegram_id)
            # upon successful login because we bound it during initialization.
            await update.message.reply_text(
                "🎉 <b>Авторизация успешна!</b>\n\n"
                "Ваш профиль сохранён. Теперь вы можете использовать кнопку «🛒 В корзину» "
                "под товарами, и они будут мгновенно добавлены в вашу корзину приложения ВкусВилл.",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                "❌ Неверный код или время ожидания истекло. Начните заново с /login."
            )
            
    except Exception as e:
        logger.error(f"Error during login (code stage): {e}")
        await update.message.reply_text("❌ Произошла ошибка при проверке кода.")
    finally:
        # Always close the browser when done with login!
        await _cleanup_scraper(telegram_id)

    return ConversationHandler.END


async def cancel_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    telegram_id = update.effective_user.id

    await update.message.reply_text("Авторизация отменена.")

    await _cleanup_scraper(telegram_id)
    return ConversationHandler.END


async def _cleanup_scraper(telegram_id: int):
    """Close and remove scraper for a user, if any."""
    if telegram_id in _scrapers:
        try:
            await _scrapers[telegram_id].close()
        except Exception:
            pass
        del _scrapers[telegram_id]


async def _timeout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Called when conversation_timeout fires — clean up leaked scraper."""
    telegram_id = context.user_data.get("_login_telegram_id")
    if telegram_id:
        await _cleanup_scraper(telegram_id)
    return ConversationHandler.END


def get_login_conv_handler() -> ConversationHandler:
    """Returns the ConversationHandler for the /login command."""
    return ConversationHandler(
        entry_points=[CommandHandler("login", login_start)],
        states={
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_phone)],
            CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_code)],
            ConversationHandler.TIMEOUT: [MessageHandler(filters.ALL, _timeout_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel_login)],
        conversation_timeout=300  # 5 minutes timeout
    )

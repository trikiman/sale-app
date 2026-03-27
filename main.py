"""
VkusVill Sale Monitor - Main Entry Point
Telegram bot that monitors VkusVill for sales and green prices.
Scraping is handled by scheduler_service.py — this file only runs the Telegram bot.
"""
import logging

from telegram.ext import Application

import config
from bot.handlers import setup_handlers
from database.db import get_database


# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point — starts Telegram bot only.
    Scraping is handled separately by scheduler_service.py.
    """
    logger.info("Starting VkusVill Sale Monitor Bot...")

    # Initialize database
    get_database()
    logger.info("Database initialized")

    # Create Telegram application
    application = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .build()
    )

    # Set up handlers
    setup_handlers(application)

    # Run bot
    logger.info("Bot is starting...")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

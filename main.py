"""
VkusVill Sale Monitor - Main Entry Point
Telegram bot that monitors VkusVill for sales and green prices
"""
import asyncio
import logging
from datetime import datetime, timedelta

from telegram.ext import Application
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

import config
from bot.handlers import setup_handlers
from bot.notifier import get_notifier, Notifier
from scraper.vkusvill import get_scraper, close_scraper
from database.db import get_database


# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def check_sales_job(notifier: Notifier):
    """Scheduled job to check for sales and notify users"""
    logger.info("Running scheduled sales check...")
    
    try:
        scraper = get_scraper()
        db = get_database()
        
        # Check if logged in
        is_logged = await scraper.is_logged_in()
        if not is_logged:
            logger.warning("Not logged in to VkusVill! Run 'python login.py' first.")
            return
        
        # Fetch green prices
        products = await scraper.fetch_all_green_prices()
        
        if not products:
            logger.info("No green price products found")
            return
        
        logger.info(f"Found {len(products)} green price products")
        
        # Notify users about products matching their favorites
        await notifier.notify_new_green_prices(products)
        
        # Cleanup old data periodically
        db.cleanup_old_data(days=7)
        
        logger.info("Sales check completed")
        
    except Exception as e:
        logger.error(f"Error in sales check job: {e}", exc_info=True)


async def post_init(application: Application):
    """Called after the application is initialized"""
    logger.info("Bot post-init: setting up scheduler...")
    
    # Initialize notifier with bot instance
    notifier = get_notifier(application.bot)
    
    # Set up scheduler for periodic checks
    scheduler = AsyncIOScheduler()
    
    # Store scheduler in bot_data so we can access it later
    application.bot_data['scheduler'] = scheduler
    application.bot_data['notifier'] = notifier
    
    # Schedule sales check every 5 minutes
    scheduler.add_job(
        check_sales_job,
        trigger=IntervalTrigger(seconds=config.POLLING_INTERVAL),
        args=[notifier],
        id='check_sales',
        name='Check for sales',
        replace_existing=True
    )
    
    # Run initial check after 30 seconds
    scheduler.add_job(
        check_sales_job,
        trigger='date',
        run_date=datetime.now() + timedelta(seconds=30),
        args=[notifier],
        id='initial_check',
        name='Initial sales check'
    )
    
    logger.info(f"Scheduler configured: checking every {config.POLLING_INTERVAL // 60} minutes")
    
    # Start scheduler
    scheduler.start()
    logger.info("Scheduler started")


async def post_shutdown(application: Application):
    """Called when the application is shutting down"""
    logger.info("Bot shutting down...")
    
    scheduler = application.bot_data.get('scheduler')
    if scheduler:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
    
    # Close the scraper (browser)
    await close_scraper()
    logger.info("Scraper closed")


def main():
    """Main entry point"""
    logger.info("Starting VkusVill Sale Monitor Bot...")
    
    # Check for browser state file
    import os
    browser_state_path = os.path.join(os.path.dirname(config.DATABASE_PATH), "browser_state.json")
    if not os.path.exists(browser_state_path):
        logger.warning("=" * 60)
        logger.warning("Browser state not found!")
        logger.warning("You need to log in first. Run: python login.py")
        logger.warning("=" * 60)
    else:
        logger.info(f"Browser state found: {browser_state_path}")
    
    # Initialize database
    db = get_database()
    logger.info("Database initialized")
    
    # Create Telegram application with post_init callback
    application = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    
    # Set up handlers
    setup_handlers(application)
    
    # Run bot
    logger.info("Bot is starting...")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

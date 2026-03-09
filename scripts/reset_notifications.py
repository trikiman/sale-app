"""
Reset notification state for testing.
Clears seen_products and notifications tables so all current products
appear as "new" on the next notifier run, triggering favorite alerts.

Usage:
    python scripts/reset_notifications.py           # reset only
    python scripts/reset_notifications.py --notify  # reset + run notifier immediately
"""
import sys
import os
import sqlite3
import asyncio
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

DB_PATH = config.DATABASE_PATH


def reset(db_path: str):
    if not os.path.exists(db_path):
        print(f"DB not found: {db_path}")
        sys.exit(1)

    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM seen_products")
        seen_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM notifications")
        notif_count = cur.fetchone()[0]

        cur.execute("DELETE FROM seen_products")
        cur.execute("DELETE FROM notifications")
        conn.commit()

    print(f"  Cleared {seen_count} seen_products rows")
    print(f"  Cleared {notif_count} notifications rows")
    print("  Reset done — all products will appear as new on next notifier run")


async def run_notifier():
    from backend.notifier import ProductNotifier
    import config as cfg

    bot_token = getattr(cfg, 'TELEGRAM_BOT_TOKEN', None) or os.getenv('TELEGRAM_BOT_TOKEN')
    admin_id = getattr(cfg, 'ADMIN_CHAT_ID', None) or os.getenv('ADMIN_CHAT_ID')
    if admin_id:
        admin_id = int(admin_id)

    if not bot_token:
        print("  No TELEGRAM_BOT_TOKEN found — skipping notifier run")
        return

    print(f"  Running notifier (admin_id={admin_id})...")
    notifier = ProductNotifier(bot_token=bot_token)
    await notifier.run_notification_cycle(admin_chat_id=admin_id)
    print("  Notifier run complete")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--notify", action="store_true", help="Run notifier after reset")
    args = parser.parse_args()

    print(f"DB: {DB_PATH}")
    reset(DB_PATH)

    if args.notify:
        asyncio.run(run_notifier())
    else:
        print("\nTip: run with --notify to trigger the bot immediately after reset")

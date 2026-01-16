"""
VkusVill Auto-Scraper
Runs every 5 minutes to keep Mini App data fresh
"""
import time
import schedule
from datetime import datetime
from scrape_prices import main as scrape_all_prices


def run_scraper():
    """Run the scraper and log results"""
    print(f"\n{'='*60}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting scheduled scrape...")
    print(f"{'='*60}")

    try:
        # Run the full scraping cycle (Green, Red, Yellow)
        scrape_all_prices()
        print(f"✅ Scheduled scrape completed successfully")
    except Exception as e:
        print(f"❌ Scrape error: {e}")

    print(f"Next run in 5 minutes...")


def main():
    print("=" * 60)
    print("VkusVill Auto-Scraper")
    print("Runs every 5 minutes to keep data fresh")
    print("=" * 60)
    print("\n⚠️  First time setup:")
    print("1. Run 'python scrape_prices.py' once manually")
    print("2. Log in to VkusVill in the browser")
    print("3. Then run this scheduler\n")
    
    # Run immediately on start
    run_scraper()
    
    # Schedule every 5 minutes
    schedule.every(5).minutes.do(run_scraper)
    
    print("\n🔄 Scheduler running. Press Ctrl+C to stop.\n")
    
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()

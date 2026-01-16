"""
Background Scheduler for VkusVill Scraper
Runs scraper every 5 minutes without Windows Task Scheduler
"""
import time
import subprocess
import os
import sys
from datetime import datetime

# Configuration
INTERVAL_MINUTES = 5
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRAPER_PATH = os.path.join(SCRIPT_DIR, "scrape_prices.py")
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")

os.makedirs(LOG_DIR, exist_ok=True)


def log(message):
    """Log with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")
    
    # Also write to file
    log_file = os.path.join(LOG_DIR, "scheduler.log")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


def run_scraper():
    """Run the scraper once"""
    log("Starting scrape...")
    
    try:
        result = subprocess.run(
            [sys.executable, SCRAPER_PATH],
            cwd=SCRIPT_DIR,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode == 0:
            log("Scrape completed successfully")
            
            # Copy data to miniapp
            src = os.path.join(SCRIPT_DIR, "data", "proposals.json")
            dst = os.path.join(SCRIPT_DIR, "miniapp", "public", "data.json")
            if os.path.exists(src):
                import shutil
                shutil.copy2(src, dst)
                log("Data copied to miniapp")
            
            return True
        else:
            log(f"Scrape failed with code {result.returncode}")
            log(f"Error: {result.stderr[:500] if result.stderr else 'No error output'}")
            return False
            
    except subprocess.TimeoutExpired:
        log("Scrape timed out after 5 minutes")
        return False
    except Exception as e:
        log(f"Scrape error: {e}")
        return False


def main():
    """Main scheduler loop"""
    log("=" * 50)
    log("VkusVill Scheduler Started")
    log(f"Interval: {INTERVAL_MINUTES} minutes")
    log("Press Ctrl+C to stop")
    log("=" * 50)
    
    while True:
        try:
            run_scraper()
            
            log(f"Sleeping for {INTERVAL_MINUTES} minutes...")
            time.sleep(INTERVAL_MINUTES * 60)
            
        except KeyboardInterrupt:
            log("Scheduler stopped by user")
            break
        except Exception as e:
            log(f"Scheduler error: {e}")
            time.sleep(60)  # Wait 1 minute before retry


if __name__ == "__main__":
    main()

"""
Scheduler service — runs scrapers sequentially then merge.
Runs every 5 minutes.

BUG FIXES Applied:
- BUG-1: Run scrapers SEQUENTIALLY (not parallel) to avoid Chrome conflicts
- BUG-2: Detect scraper failures even when exit code is 0 (check file mtime)
- BUG-4: All output goes to scheduler.log with [SCRAPER_NAME] prefixes
"""
import time
import subprocess
import sys
import os
from datetime import datetime

# Fix Windows console encoding for emoji in scraper output
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Configuration
INTERVAL_MINUTES = 3
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(os.path.join(LOG_DIR, "backend"), exist_ok=True)  # BUG-3: notifier log dir

LOG_FILE = os.path.join(LOG_DIR, "scheduler.log")


def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _log_script_output(script_name, output_text, tag=None):
    """Write script output lines into scheduler.log with [TAG] prefix."""
    tag = tag or script_name.replace("scrape_", "").replace(".py", "").upper()
    if not output_text:
        return
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        for line in output_text.strip().splitlines():
            entry = f"    [{tag}] {line}\n"
            try:
                print(f"  [{tag}] {line}", flush=True)
            except UnicodeEncodeError:
                # Console codepage can't handle emoji — print ascii-safe version
                safe = line.encode('ascii', errors='replace').decode('ascii')
                print(f"  [{tag}] {safe}", flush=True)
            f.write(entry)


def run_script(script_name, tag=None):
    """Run a script, log ALL output into scheduler.log. Returns exit code."""
    script_path = os.path.join(BASE_DIR, script_name)
    tag = tag or script_name.replace("scrape_", "").replace(".py", "").upper()
    log(f"Starting {script_name}...")
    try:
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=BASE_DIR,
            env=env,
        )
        # Log ALL output into scheduler.log with tag prefix
        _log_script_output(script_name, result.stdout, tag)
        if result.stderr:
            _log_script_output(script_name, result.stderr, f"{tag}-ERR")

        if result.returncode != 0:
            log(f"ERROR {script_name} exited {result.returncode}")
        else:
            log(f"OK {script_name} finished (exit 0)")
        return result.returncode
    except Exception as e:
        log(f"EXCEPTION launching {script_name}: {e}")
        return -1


def _kill_orphan_chromes():
    """Kill Chrome processes from previous scraper runs (temp profiles starting with uc_).
    Prevents zombie Chrome accumulation over hours of scraping."""
    if sys.platform != 'win32':
        return
    try:
        result = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq chrome.exe', '/FO', 'CSV', '/V'],
            capture_output=True, text=True, timeout=10
        )
        killed = 0
        for line in result.stdout.splitlines():
            if 'uc_' in line:
                parts = line.strip().split(',')
                try:
                    pid = int(parts[1].strip('"'))
                    os.kill(pid, 9)
                    killed += 1
                except (ValueError, OSError, IndexError):
                    pass
        if killed:
            log(f"Killed {killed} orphan Chrome processes")
    except Exception:
        pass


def _check_file_updated(path, before_ts):
    """Check if a file was modified after before_ts. Returns True if updated."""
    if not os.path.exists(path):
        return False
    return os.path.getmtime(path) > before_ts


def run_full_cycle():
    _kill_orphan_chromes()
    log("=" * 60)
    log("=== Starting Scrape Cycle ===")
    log("=" * 60)

    # Run all 3 scrapers sequentially — each gets its own Chrome port
    scrapers = [
        ("scrape_red.py", "RED", "red_products.json"),
        ("scrape_yellow.py", "YELLOW", "yellow_products.json"),
        ("scrape_green.py", "GREEN", "green_products.json"),  # last = freshest
    ]

    scraper_results = {}
    for script, tag, data_file in scrapers:
        data_path = os.path.join(DATA_DIR, data_file)
        before_ts = os.path.getmtime(data_path) if os.path.exists(data_path) else 0

        code = run_script(script, tag)

        file_updated = _check_file_updated(data_path, before_ts)

        if code != 0:
            status = f"ERROR (exit {code})"
        elif not file_updated:
            status = "WARNING (exit 0 but data NOT updated)"
        else:
            status = "OK (data updated)"

        scraper_results[tag] = status
        log(f"  {tag}: {status}")

    _kill_orphan_chromes()

    # Run merge after all scrapers complete
    log("Running merge...")
    run_script("scrape_merge.py", "MERGE")

    # Send Telegram notifications for favorites that are now on sale
    log("Running favorite notifications...")
    run_script(os.path.join("backend", "notifier.py"), "NOTIF")

    # Summary
    log("-" * 60)
    log("Cycle Summary:")
    for tag, status in scraper_results.items():
        log(f"  {tag}: {status}")
    log("=" * 60)


def main():
    log(f"Scheduler service started. Interval: {INTERVAL_MINUTES} minutes.")
    log(f"Logs: {LOG_FILE}")

    while True:
        try:
            run_full_cycle()
            log(f"Waiting {INTERVAL_MINUTES} minutes for next cycle...")
            time.sleep(INTERVAL_MINUTES * 60)
        except KeyboardInterrupt:
            log("Scheduler stopped by user.")
            break
        except Exception as e:
            log(f"Unexpected error in main loop: {e}")
            time.sleep(60)


if __name__ == "__main__":
    main()

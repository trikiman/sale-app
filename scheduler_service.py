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
PAUSE_FILE = os.path.join(DATA_DIR, "login_pause")
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


SCRAPER_TIMEOUT = 120  # ultimate safety net (seconds)

# Lines matching these → instant kill + retry with proxy
KILL_TRIGGERS = [
    "blocked (403)",
    "forbidden",
    "vkusvill not available",
    "err_proxy",
    "err_connection",
]


def _is_kill_trigger(line: str) -> str | None:
    """Check if a log line indicates a block/timeout. Returns matched trigger or None."""
    lower = line.lower()
    for trigger in KILL_TRIGGERS:
        if trigger in lower:
            return trigger
    return None


def run_script(script_name, tag=None):
    """Run a script with real-time output parsing.
    Returns: 0 = OK, non-zero = error, -2 = block/timeout detected (retry candidate)."""
    script_path = os.path.join(BASE_DIR, script_name)
    tag = tag or script_name.replace("scrape_", "").replace(".py", "").upper()
    log(f"Starting {script_name}...")

    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'

    try:
        proc = subprocess.Popen(
            [sys.executable, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # merge stderr into stdout
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=BASE_DIR,
            env=env,
        )
    except Exception as e:
        log(f"EXCEPTION launching {script_name}: {e}")
        return -1

    killed_by_trigger = None
    start_time = time.time()

    # Stream output line by line, check for kill triggers
    try:
        for line in proc.stdout:
            line = line.rstrip('\n\r')
            # Log to file + console
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"    [{tag}] {line}\n")
            try:
                print(f"  [{tag}] {line}", flush=True)
            except UnicodeEncodeError:
                safe = line.encode('ascii', errors='replace').decode('ascii')
                print(f"  [{tag}] {safe}", flush=True)

            # Check for kill trigger
            trigger = _is_kill_trigger(line)
            if trigger:
                killed_by_trigger = trigger
                log(f"KILL TRIGGER detected in {script_name}: '{trigger}' — killing immediately")
                proc.kill()
                break

            # Safety net: hard timeout
            if time.time() - start_time > SCRAPER_TIMEOUT:
                log(f"TIMEOUT {script_name} killed after {SCRAPER_TIMEOUT}s")
                proc.kill()
                return -2
    except Exception as e:
        log(f"Error reading output from {script_name}: {e}")

    proc.wait(timeout=10)

    if killed_by_trigger:
        return -2  # trigger retry

    if proc.returncode != 0:
        log(f"ERROR {script_name} exited {proc.returncode}")
    else:
        log(f"OK {script_name} finished (exit 0)")
    return proc.returncode


def _kill_orphan_chromes():
    """Kill only ORPHAN Chrome (uc_ temp profiles from green scraper).
    Does NOT kill the main CDP Chrome on port 19222 — red/yellow need it."""
    if sys.platform != 'win32':
        return
    try:
        import psutil
    except ImportError:
        return
    killed = 0
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if (proc.name() or "").lower() != "chrome.exe":
                continue
            cmdline = " ".join(proc.cmdline()).lower()
            # Only kill temp-profile chromes, NOT the main CDP one
            if "uc_" in cmdline and "remote-debugging-port" not in cmdline:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True, timeout=5
                )
                killed += 1
        except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
            continue
    if killed:
        log(f"Killed {killed} orphan Chrome process(es)")


def _kill_all_scraper_chrome():
    """Kill ALL scraper Chrome (including main CDP on 19222).
    Used before restarting Chrome with a new proxy."""
    if sys.platform != 'win32':
        return
    try:
        import psutil
    except ImportError:
        subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'], capture_output=True)
        return
    killed = 0
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if (proc.name() or "").lower() != "chrome.exe":
                continue
            cmdline = " ".join(proc.cmdline()).lower()
            if "remote-debugging-port" in cmdline or "uc_" in cmdline:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True, timeout=5
                )
                killed += 1
        except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
            continue
    if killed:
        log(f"Killed {killed} scraper Chrome process(es)")


def _check_file_updated(path, before_ts):
    """Check if a file was modified after before_ts. Returns True if updated."""
    if not os.path.exists(path):
        return False
    return os.path.getmtime(path) > before_ts


def run_full_cycle(proxy_state):
    """Run a full scrape cycle. Returns updated proxy_state dict."""
    _kill_orphan_chromes()  # only orphans, keep main CDP Chrome alive
    log("=" * 60)
    log("=== Starting Scrape Cycle ===")
    log("=" * 60)

    # ── Proxy check: is VkusVill reachable? ──
    from proxy_manager import ProxyManager
    pm = ProxyManager(log_func=log)

    current_proxy = proxy_state.get("active_proxy")

    if pm.check_direct():
        # Direct works — if we were using proxy, switch back
        if current_proxy:
            log("VkusVill reachable directly — switching Chrome back to direct mode")
            from chrome_stealth import restart_chrome_with_proxy
            restart_chrome_with_proxy(proxy=None, tag="PROXY")
            proxy_state["active_proxy"] = None
        log("VkusVill: OK (direct)")
    else:
        log("VkusVill: BLOCKED (direct connection failed)")
        # Find a working proxy
        proxy = pm.get_working_proxy()
        if proxy:
            proxy_url = f"socks5://{proxy}"
            if proxy_url != current_proxy:
                log(f"Switching Chrome to proxy: {proxy_url}")
                from chrome_stealth import restart_chrome_with_proxy
                restart_chrome_with_proxy(proxy=proxy_url, tag="PROXY")
                proxy_state["active_proxy"] = proxy_url
            else:
                log(f"Already using proxy: {proxy_url}")
        else:
            log("WARNING: VkusVill blocked and no working proxy found. Cycle will likely fail.")

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

        # ── Timeout or block → kill + proxy + retry once ──
        if code == -2 or code == 1:  # -2 = timeout, 1 = scraper error (likely block)
            log(f"  {tag}: {'TIMEOUT' if code == -2 else 'FAILED'} — attempting kill + proxy + retry")

            # 1. Kill ALL scraper Chrome (will restart with proxy)
            _kill_all_scraper_chrome()

            # 2. Pick next proxy (removes the dead one from pool)
            proxy = pm.next_proxy()
            if proxy:
                proxy_url = f"socks5://{proxy}"
                log(f"  Restarting Chrome with proxy: {proxy_url}")
                from chrome_stealth import restart_chrome_with_proxy
                restart_chrome_with_proxy(proxy=proxy_url, tag="PROXY")
                proxy_state["active_proxy"] = proxy_url
                time.sleep(3)  # let Chrome stabilize

                # 3. Retry the scraper once
                before_ts = os.path.getmtime(data_path) if os.path.exists(data_path) else 0
                code = run_script(script, f"{tag}-RETRY")
            else:
                log(f"  No working proxy found — skipping retry")

        file_updated = _check_file_updated(data_path, before_ts)

        if code == -2:
            status = "TIMEOUT (even after retry)"
        elif code != 0:
            status = f"ERROR (exit {code})"
        elif not file_updated:
            status = "WARNING (exit 0 but data NOT updated)"
        else:
            status = "OK (data updated)"

        scraper_results[tag] = status
        log(f"  {tag}: {status}")

    _kill_all_scraper_chrome()
    proxy_state["active_proxy"] = None  # next cycle starts fresh Chrome

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
    if proxy_state.get("active_proxy"):
        log(f"  PROXY: {proxy_state['active_proxy']}")
    log("=" * 60)

    # Track consecutive failures for circuit breaker
    all_failed = all("ERROR" in s for s in scraper_results.values())
    if all_failed:
        proxy_state["consecutive_fails"] = proxy_state.get("consecutive_fails", 0) + 1
    else:
        proxy_state["consecutive_fails"] = 0

    return proxy_state


def main():
    log(f"Scheduler service started. Interval: {INTERVAL_MINUTES} minutes.")
    log(f"Logs: {LOG_FILE}")

    proxy_state = {
        "active_proxy": None,
        "consecutive_fails": 0,
    }

    while True:
        try:
            # Check if login is active — pause scrapers to let Chrome be used for login
            if os.path.exists(PAUSE_FILE):
                log("Login in progress — pausing scrapers...")
                while os.path.exists(PAUSE_FILE):
                    time.sleep(5)
                log("Login finished — resuming scrapers.")
                time.sleep(3)  # Give Chrome a moment to settle

            proxy_state = run_full_cycle(proxy_state)

            # Circuit breaker: if 3+ consecutive all-fail cycles, wait longer
            fails = proxy_state.get("consecutive_fails", 0)
            if fails >= 3:
                wait = 10  # minutes
                log(f"Circuit breaker: {fails} consecutive failures. Waiting {wait} min instead of {INTERVAL_MINUTES}.")
                # Also try refreshing proxy list for next attempt
                try:
                    from proxy_manager import ProxyManager
                    pm = ProxyManager(log_func=log)
                    pm.refresh_proxy_list()
                except Exception:
                    pass
            else:
                wait = INTERVAL_MINUTES

            log(f"Waiting {wait} minutes for next cycle...")
            time.sleep(wait * 60)
        except KeyboardInterrupt:
            log("Scheduler stopped by user.")
            break
        except Exception as e:
            log(f"Unexpected error in main loop: {e}")
            time.sleep(60)


if __name__ == "__main__":
    main()


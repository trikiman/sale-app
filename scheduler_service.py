import time
import subprocess
import sys
import os
from datetime import datetime

# Configuration
INTERVAL_MINUTES = 5
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)


def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line, flush=True)
    with open(os.path.join(LOG_DIR, "scheduler.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run_script(script_name):
    """Run a scraper and capture + display its output. Returns exit code."""
    script_path = os.path.join(BASE_DIR, script_name)
    log_path = os.path.join(LOG_DIR, script_name.replace(".py", ".log"))
    log(f"Starting {script_name}...")
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=BASE_DIR,
        )
        # Write to individual log file
        with open(log_path, "w", encoding="utf-8") as lf:
            lf.write(result.stdout or "")
            if result.stderr:
                lf.write("\n--- STDERR ---\n")
                lf.write(result.stderr)

        # Print last few lines to terminal for visibility
        lines = (result.stdout or "").strip().splitlines()
        if lines:
            for line in lines[-5:]:  # last 5 lines
                print(f"  [{script_name}] {line}", flush=True)
        if result.returncode != 0:
            log(f"ERROR {script_name} exited {result.returncode}")
            if result.stderr:
                print(f"  [{script_name}] STDERR: {result.stderr[:500]}", flush=True)
        else:
            log(f"OK {script_name} finished (exit 0)")
        return result.returncode
    except Exception as e:
        log(f"EXCEPTION launching {script_name}: {e}")
        return -1


def run_full_cycle():
    log("=== Starting Scrape Cycle ===")

    scrapers = ["scrape_green.py", "scrape_red.py", "scrape_yellow.py"]

    # Start all scrapers in parallel (Popen = non-blocking)
    processes = []
    for script in scrapers:
        script_path = os.path.join(BASE_DIR, script)
        log_path = os.path.join(LOG_DIR, script.replace(".py", ".log"))
        log(f"Launching {script} (parallel)...")
        try:
            p = subprocess.Popen(
                [sys.executable, script_path],
                stdout=open(log_path, "w", encoding="utf-8"),
                stderr=subprocess.STDOUT,
                cwd=BASE_DIR,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            processes.append((script, p, log_path))
        except Exception as e:
            log(f"Failed to start {script}: {e}")

    # Wait for all scrapers to finish, with 10-minute timeout per scraper
    # (prevents infinite hang when Chrome startup blocks indefinitely)
    SCRAPER_TIMEOUT = 10 * 60  # 10 minutes
    for script, p, log_path in processes:
        try:
            p.wait(timeout=SCRAPER_TIMEOUT)
            code = p.returncode
            status = "OK" if code == 0 else f"ERROR (exit {code})"
        except Exception:
            # Timeout or other error — kill the hung process
            try:
                p.kill()
            except Exception:
                pass
            code = -1
            status = f"TIMEOUT (killed after {SCRAPER_TIMEOUT//60}min)"
        log(f"{status}: {script}")
        # Show last 5 lines of output
        try:
            with open(log_path, encoding="utf-8", errors="replace") as lf:
                lines = lf.read().strip().splitlines()
            if lines:
                for line in lines[-5:]:
                    print(f"  [{script}] {line}", flush=True)
        except Exception:
            pass

    # Run merge after all scrapers complete
    log("Running merge...")
    run_script("scrape_merge.py")
    log("=== Cycle Completed ===")


def main():
    log(f"Scheduler service started. Interval: {INTERVAL_MINUTES} minutes.")
    log(f"Logs in: {LOG_DIR}")

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

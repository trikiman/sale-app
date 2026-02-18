import time
import subprocess
import sys
import os
from datetime import datetime

# Configuration
INTERVAL_MINUTES = 5
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def run_script(script_name):
    script_path = os.path.join(BASE_DIR, script_name)
    log(f"Running {script_name}...")
    try:
        # Using sys.executable to ensure we use the same python interpreter
        result = subprocess.run([sys.executable, script_path], check=True, capture_output=True, text=True)
        log(f"Successfully finished {script_name}")
        return True
    except subprocess.CalledProcessError as e:
        log(f"Error running {script_name}: {e}")
        if e.stdout: print(f"STDOUT: {e.stdout}")
        if e.stderr: print(f"STDERR: {e.stderr}")
        return False

def run_full_cycle():
    log("=== Starting Scrape Cycle ===")

    # Define scrapers to run in parallel
    scrapers = ["scrape_green.py", "scrape_red.py", "scrape_yellow.py"]
    processes = []

    # Start all scrapers
    for script in scrapers:
        script_path = os.path.join(BASE_DIR, script)
        log(f"Starting {script}...")
        try:
            # Popen starts the process without blocking
            p = subprocess.Popen([sys.executable, script_path], text=True)
            processes.append((script, p))
        except Exception as e:
            log(f"Failed to start {script}: {e}")

    # Wait for all scrapers to finish
    for script, p in processes:
        p.wait()
        if p.returncode == 0:
            log(f"Successfully finished {script}")
        else:
            log(f"Error in {script} (Exit code: {p.returncode})")

    # Run merge script after all scrapers are done
    run_script("scrape_merge.py")

    log("=== Cycle Completed ===")

def main():
    log(f"Scheduler service started. Interval: {INTERVAL_MINUTES} minutes.")
    
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

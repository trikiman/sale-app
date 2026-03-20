"""
Kill Chrome + Scheduler + Scrapers — clean slate for the scraping pipeline.

Usage:  python kill_chrome.py
"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import psutil
import subprocess
import os

WORKSPACE = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_LOWER = WORKSPACE.lower().replace("/", "\\")


def _get_parent_pids() -> set[int]:
    """Don't kill our own process tree."""
    pids = set()
    try:
        proc = psutil.Process(os.getpid())
        while proc:
            pids.add(proc.pid)
            proc = proc.parent()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    return pids


def find_targets() -> list[dict]:
    """Find Chrome + scheduler + scraper processes."""
    exclude = _get_parent_pids()
    results = []

    for proc in psutil.process_iter(["pid", "name"]):
        if proc.pid in exclude:
            continue
        try:
            name = (proc.name() or "").lower()
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue

        try:
            cmdline = " ".join(proc.cmdline())
        except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
            cmdline = "?"

        cmdline_lower = cmdline.lower().replace("/", "\\")
        label = None

        # ── Chrome (ONLY scraper Chrome, not personal browser) ──
        if name == "chrome.exe":
            # Scraper Chrome has: --remote-debugging-port or uc_ profile dir
            is_scraper_chrome = (
                "remote-debugging-port" in cmdline_lower
                or "uc_scraper_" in cmdline_lower
                or "uc_" in cmdline_lower
            )
            if is_scraper_chrome:
                if "remote-debugging-port" in cmdline_lower:
                    label = "Chrome (CDP / scraper)"
                elif "--proxy-server" in cmdline_lower:
                    label = "Chrome (proxy)"
                else:
                    label = "Chrome (scraper child)"
            else:
                # Personal Chrome — skip it
                continue

        # ── Scheduler / Scrapers (only from our workspace) ──
        elif name in ("python.exe", "python3.exe"):
            in_ws = WORKSPACE_LOWER in cmdline_lower
            if not in_ws:
                try:
                    cwd = (proc.cwd() or "").lower().replace("/", "\\")
                    in_ws = WORKSPACE_LOWER in cwd
                except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
                    pass

            if in_ws:
                if "scheduler_service.py" in cmdline_lower:
                    label = "Scheduler"
                elif "scrape_green.py" in cmdline_lower:
                    label = "Scraper (green)"
                elif "scrape_red.py" in cmdline_lower:
                    label = "Scraper (red)"
                elif "scrape_yellow.py" in cmdline_lower:
                    label = "Scraper (yellow)"
                elif "scrape_merge.py" in cmdline_lower:
                    label = "Scraper (merge)"
                elif "scrape_categories.py" in cmdline_lower:
                    label = "Scraper (categories)"

        if label:
            results.append({
                "pid": proc.pid,
                "label": label,
                "cmd": cmdline[:120] or "?",
            })

    return results


def kill_all(procs: list[dict]):
    seen_pids = set()
    for p in procs:
        if p["pid"] in seen_pids:
            continue
        seen_pids.add(p["pid"])
        try:
            result = subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(p["pid"])],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                print(f"  ✓ PID {p['pid']:>6}  {p['label']}")
            else:
                err = result.stderr.strip()
                if "not found" in err.lower():
                    print(f"  - PID {p['pid']:>6}  already dead")
                elif "access is denied" in err.lower() or "could not be terminated" in err.lower():
                    print(f"  - PID {p['pid']:>6}  protected child (dies with parent)")
                else:
                    print(f"  ⚠ PID {p['pid']:>6}  {err}")
        except Exception as e:
            print(f"  ⚠ PID {p['pid']:>6}  {e}")


def main():
    print("🔍 Scanning for Chrome + Scheduler + Scraper processes...\n")
    procs = find_targets()

    if not procs:
        print("✅ Nothing running. All clean.")
        return

    print(f"Found {len(procs)} process(es):\n")
    print(f"  {'PID':>6}  {'Type':<25} {'Command'}")
    print(f"  {'---':>6}  {'---':<25} {'---'}")
    for p in procs:
        print(f"  {p['pid']:>6}  {p['label']:<25} {p['cmd'][:80]}")

    print("\n🔪 Killing...\n")
    kill_all(procs)
    print("\n✅ Done.")


if __name__ == "__main__":
    main()

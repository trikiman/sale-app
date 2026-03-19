"""
Kill all processes launched by run_app.bat / run_scrapers.bat:
  - python main.py              (Telegram Bot)
  - uvicorn backend.main:app    (FastAPI backend)
  - python scheduler_service.py (Scheduler)
  - scrape_*.py                 (Scrapers)
  - cmd.exe windows hosting them

Usage:  python kill_workspace.py
"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import psutil
import subprocess
import os
import sys

WORKSPACE = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_LOWER = WORKSPACE.lower().replace("/", "\\")


def get_cmdline_str(proc):
    try:
        return " ".join(proc.cmdline())
    except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
        return ""


def get_cwd(proc):
    try:
        return proc.cwd() or ""
    except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
        return ""


def is_workspace_process(proc) -> str | None:
    """Return a label if this process belongs to the workspace, else None."""
    try:
        name = (proc.name() or "").lower()
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        return None

    # Only check python and cmd processes
    if name not in ("python.exe", "python3.exe", "cmd.exe"):
        return None

    cmdline = get_cmdline_str(proc).lower().replace("/", "\\")
    cwd = get_cwd(proc).lower().replace("/", "\\")

    # Check if process is related to our workspace via cwd or cmdline
    in_workspace = (
        WORKSPACE_LOWER in cwd
        or WORKSPACE_LOWER in cmdline
    )

    if not in_workspace:
        return None

    # Identify what it is
    if "main.py" in cmdline and "uvicorn" not in cmdline:
        return "Telegram Bot (main.py)"
    if "uvicorn" in cmdline and "backend.main" in cmdline:
        return "Backend (uvicorn)"
    if "scheduler_service.py" in cmdline:
        return "Scheduler"
    if "scrape_green.py" in cmdline:
        return "Scraper (green)"
    if "scrape_red.py" in cmdline:
        return "Scraper (red)"
    if "scrape_yellow.py" in cmdline:
        return "Scraper (yellow)"
    if "scrape_merge.py" in cmdline:
        return "Scraper (merge)"
    if "scrape_categories.py" in cmdline:
        return "Scraper (categories)"

    # cmd.exe hosting one of our processes
    if name == "cmd.exe":
        return "cmd window"

    # Any other python from our workspace
    return "python process"


def _get_parent_pids() -> set[int]:
    """Get all ancestor PIDs so we don't kill the cmd.exe running our bat."""
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
    exclude_pids = _get_parent_pids()
    results = []
    for proc in psutil.process_iter(["pid", "name"]):
        if proc.pid in exclude_pids:
            continue
        label = is_workspace_process(proc)
        if label:
            cmd_display = get_cmdline_str(proc)[:120] or "?"
            results.append({"pid": proc.pid, "label": label, "cmd": cmd_display})
    return results


def kill_all(procs: list[dict]):
    # Use taskkill /F /T to force-kill entire process trees on Windows
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
                # Already killed as part of another tree
                err = result.stderr.strip()
                if "not found" in err.lower():
                    print(f"  - PID {p['pid']:>6}  already dead")
                else:
                    print(f"  ⚠ PID {p['pid']:>6}  {err}")
        except Exception as e:
            print(f"  ⚠ PID {p['pid']:>6}  {e}")


def main():
    print(f"🔍 Scanning for saleapp processes...\n")
    procs = find_targets()

    if not procs:
        print("✅ Nothing running. All clean.")
        return

    print(f"Found {len(procs)} process(es):\n")
    print(f"  {'PID':>6}  {'What':<30} {'Command'}")
    print(f"  {'---':>6}  {'---':<30} {'---'}")
    for p in procs:
        print(f"  {p['pid']:>6}  {p['label']:<30} {p['cmd'][:80]}")

    print("\n🔪 Killing...\n")
    kill_all(procs)
    print("\n✅ Done.")


if __name__ == "__main__":
    main()

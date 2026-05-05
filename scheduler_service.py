"""
Scheduler service — runs scrapers sequentially then merge.
Runs every 5 minutes.

BUG FIXES Applied:
- BUG-1: Run scrapers SEQUENTIALLY (not parallel) to avoid Chrome conflicts
- BUG-2: Detect scraper failures even when exit code is 0 (check file mtime)
- BUG-4: All output goes to scheduler.log with [SCRAPER_NAME] prefixes
"""
from __future__ import annotations

import time
import subprocess
import sys
import os
import json
import threading
from datetime import datetime

from vless.preflight import probe_bridge_alive

# Fix Windows console encoding for emoji in scraper output
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Configuration
FULL_CYCLE_INTERVAL_SECONDS = 300
GREEN_TARGET_INTERVAL_SECONDS = 60
DEFAULT_GREEN_RUNTIME_SECONDS = 60
SCRAPER_TIMEOUT = 300  # 5 minutes max per scraper
# Watchdog: if the main loop hasn't ticked for this long, assume we're hung
# (e.g. stuck in a C-level syscall that Python timeouts can't interrupt) and
# hard-exit so systemd restarts us. Must comfortably exceed the slowest
# legitimate scraper cycle (~5 min per scrape × 3 + proxy refresh ≤ 25 min).
WATCHDOG_TIMEOUT_SECONDS = 30 * 60
WATCHDOG_CHECK_INTERVAL_SECONDS = 30
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
PAUSE_FILE = os.path.join(DATA_DIR, "login_pause")
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(os.path.join(LOG_DIR, "backend"), exist_ok=True)  # BUG-3: notifier log dir

LOG_FILE = os.path.join(LOG_DIR, "scheduler.log")
CYCLE_STATE_PATH = os.path.join(DATA_DIR, "scrape_cycle_state.json")

# Graduated circuit breaker (Phase 60 REL-07..10). States: closed / open /
# half_open. See .planning/phases/60-observatory-probe-and-circuit-breaker.
BREAKER_BASE_COOLDOWN_S = 120
BREAKER_MAX_COOLDOWN_S = 30 * 60
BREAKER_TRIP_THRESHOLD = 3
BREAKER_STATE_FILE = os.path.join(DATA_DIR, "scheduler_state.json")


def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


class BreakerState:
    """Graduated 3-state circuit breaker for the scheduler.

    States:
      - ``"closed"``: normal operation; run scrapers on schedule.
      - ``"open"``: tripped; wait until ``cooldown_until_ts`` then go to
        ``"half_open"``.
      - ``"half_open"``: probe via GREEN-only; success -> ``"closed"``,
        failure -> ``"open"`` with cooldown doubled.

    Cooldown doubles on every re-trip starting at ``BREAKER_BASE_COOLDOWN_S``,
    capped at ``BREAKER_MAX_COOLDOWN_S``. Resets to base on any successful
    scraper run (REL-09 - not just all-clean cycles).

    Persisted to ``DATA_DIR/scheduler_state.json`` across restart (REL-10);
    corrupt-file fallback creates a fresh closed breaker so the scheduler
    never crashes on a bad state file.
    """

    def __init__(
        self,
        state: str = "closed",
        cooldown_s: int = BREAKER_BASE_COOLDOWN_S,
        cooldown_until_ts: float = 0.0,
        fails: int = 0,
        last_transition_ts: float = 0.0,
    ):
        self.state = state
        self.cooldown_s = int(cooldown_s)
        self.cooldown_until_ts = float(cooldown_until_ts)
        self.fails = int(fails)
        self.last_transition_ts = float(last_transition_ts)

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "cooldown_s": self.cooldown_s,
            "cooldown_until_ts": self.cooldown_until_ts,
            "fails": self.fails,
            "last_transition_ts": self.last_transition_ts,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BreakerState":
        state = d.get("state", "closed")
        if state not in ("closed", "open", "half_open"):
            raise ValueError(f"invalid breaker state: {state!r}")
        return cls(
            state=state,
            cooldown_s=int(d.get("cooldown_s", BREAKER_BASE_COOLDOWN_S)),
            cooldown_until_ts=float(d.get("cooldown_until_ts", 0.0)),
            fails=int(d.get("fails", 0)),
            last_transition_ts=float(d.get("last_transition_ts", 0.0)),
        )

    def record_all_failed(self) -> None:
        """All scrapers failed this cycle. Advance breaker state."""
        self.fails += 1
        now = time.time()
        if self.state == "closed" and self.fails >= BREAKER_TRIP_THRESHOLD:
            self._trip(now, double=False)
        elif self.state == "half_open":
            self._trip(now, double=True)
        # state "open" during record_all_failed is impossible (we'd be in
        # cooldown and not running scrapers); safety no-op if it happens.

    def record_any_success(self) -> None:
        """Any scraper succeeded this cycle. Reset breaker to closed (REL-09)."""
        if (
            self.state != "closed"
            or self.fails > 0
            or self.cooldown_s != BREAKER_BASE_COOLDOWN_S
        ):
            self.state = "closed"
            self.fails = 0
            self.cooldown_s = BREAKER_BASE_COOLDOWN_S
            self.cooldown_until_ts = 0.0
            self.last_transition_ts = time.time()

    def _trip(self, now: float, *, double: bool) -> None:
        if double:
            self.cooldown_s = min(self.cooldown_s * 2, BREAKER_MAX_COOLDOWN_S)
        else:
            self.cooldown_s = BREAKER_BASE_COOLDOWN_S
        self.state = "open"
        self.cooldown_until_ts = now + self.cooldown_s
        self.last_transition_ts = now

    def tick(self) -> None:
        """Advance state based on wall-clock. Call each scheduler iteration."""
        if self.state == "open" and time.time() >= self.cooldown_until_ts:
            self.state = "half_open"
            self.last_transition_ts = time.time()

    def seconds_until_cooldown_expires(self) -> float:
        return max(0.0, self.cooldown_until_ts - time.time())


def _load_breaker_state() -> BreakerState:
    """Load breaker from disk; fall back to fresh closed breaker on any error."""
    try:
        with open(BREAKER_STATE_FILE, "r", encoding="utf-8") as fh:
            return BreakerState.from_dict(json.load(fh))
    except (
        FileNotFoundError,
        json.JSONDecodeError,
        ValueError,
        OSError,
        TypeError,
        KeyError,
    ) as exc:
        log(f"Breaker state load: {type(exc).__name__} - starting fresh (closed)")
        return BreakerState()


def _persist_breaker_state(breaker: BreakerState) -> None:
    """Atomically persist breaker to disk. Non-fatal on failure."""
    tmp_path = BREAKER_STATE_FILE + ".tmp"
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(breaker.to_dict(), fh, indent=2)
        os.replace(tmp_path, BREAKER_STATE_FILE)
    except OSError as exc:
        log(f"Breaker state persist failed: {exc} (continuing in-memory)")
        # Leave the tmp file; a subsequent successful write will os.replace
        # over it. Attempt best-effort cleanup here but do not raise.
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass


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


SCRAPER_TIMEOUT = 300  # seconds — green scraper: modal(40s) + add-to-cart(60s) + basket(40s) ≈ 140s

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
    import threading
    script_path = os.path.join(BASE_DIR, script_name)
    tag = tag or script_name.replace("scrape_", "").replace(".py", "").upper()
    log(f"Starting {script_name}...")

    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUNBUFFERED'] = '1'  # Force line-by-line output (no buffering)

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
    timed_out = False

    # Watchdog timer: kills process if no progress for SCRAPER_TIMEOUT seconds
    # Timer resets on each line of output (proves scraper is alive)
    watchdog = [None]  # mutable container for timer reference

    def _timeout_kill():
        nonlocal timed_out
        timed_out = True
        log(f"TIMEOUT {script_name} killed after {SCRAPER_TIMEOUT}s of no output")
        try:
            proc.kill()
        except Exception:
            pass

    def _reset_watchdog():
        if watchdog[0]:
            watchdog[0].cancel()
        watchdog[0] = threading.Timer(SCRAPER_TIMEOUT, _timeout_kill)
        watchdog[0].daemon = True
        watchdog[0].start()

    _reset_watchdog()  # Start initial watchdog

    # Stream output line by line, check for kill triggers
    try:
        for line in proc.stdout:
            _reset_watchdog()  # Reset on each line (scraper is alive)
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
    except Exception as e:
        log(f"Error reading output from {script_name}: {e}")
    finally:
        if watchdog[0]:
            watchdog[0].cancel()

    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)

    if timed_out:
        return -2

    if killed_by_trigger:
        return -2  # trigger retry

    if proc.returncode != 0:
        log(f"ERROR {script_name} exited {proc.returncode}")
    else:
        log(f"OK {script_name} finished (exit 0)")
    return proc.returncode


def _is_chrome_process(proc_name: str) -> bool:
    """Check if a process name is Chrome (cross-platform)."""
    name = (proc_name or "").lower()
    return name in ("chrome.exe", "chrome", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser")


def _kill_pid(pid: int):
    """Kill a process by PID (cross-platform)."""
    if sys.platform == 'win32':
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True, timeout=5
        )
    else:
        import signal
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _kill_orphan_chromes():
    """Kill only ORPHAN Chrome (uc_ temp profiles from green scraper).
    Does NOT kill the main CDP Chrome on port 19222 — red/yellow need it."""
    try:
        import psutil
    except ImportError:
        return
    killed = 0
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if not _is_chrome_process(proc.name()):
                continue
            cmdline = " ".join(proc.cmdline()).lower()
            # Only kill temp-profile chromes, NOT the main CDP one
            if "uc_" in cmdline and "remote-debugging-port" not in cmdline:
                _kill_pid(proc.pid)
                killed += 1
        except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
            continue
    if killed:
        log(f"Killed {killed} orphan Chrome process(es)")


def _kill_all_scraper_chrome():
    """Kill ALL scraper Chrome (including main CDP on 19222).
    Used before restarting Chrome with a new proxy."""
    try:
        import psutil
    except ImportError:
        if sys.platform == 'win32':
            subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'], capture_output=True)
        else:
            subprocess.run(['pkill', '-9', '-f', 'chrome'], capture_output=True)
        return
    killed = 0
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if not _is_chrome_process(proc.name()):
                continue
            cmdline = " ".join(proc.cmdline()).lower()
            if "remote-debugging-port" in cmdline or "uc_" in cmdline:
                _kill_pid(proc.pid)
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


def _classify_scraper_status(code, file_updated):
    if code == -2:
        return "TIMEOUT (even after retry)"
    if code != 0:
        return f"ERROR (exit {code})"
    if not file_updated:
        return "WARNING (exit 0 but data NOT updated)"
    return "OK (data updated)"


def _status_kind(status_text: str) -> str:
    upper = (status_text or "").upper()
    if upper.startswith("OK"):
        return "ok"
    if upper.startswith("TIMEOUT"):
        return "timeout"
    if upper.startswith("ERROR"):
        return "error"
    if upper.startswith("WARNING"):
        return "warning"
    if upper.startswith("SKIPPED"):
        return "skipped"
    return "unknown"


def _source_state_entry(tag: str, data_file: str, status_text: str, ran_this_cycle: bool):
    path = os.path.join(DATA_DIR, data_file)
    exists = os.path.exists(path)
    updated_at = None
    age_minutes = None
    if exists:
        mtime = os.path.getmtime(path)
        updated_at = datetime.fromtimestamp(mtime).isoformat(timespec="seconds")
        age_minutes = round((time.time() - mtime) / 60, 1)

    if not ran_this_cycle:
        status_kind = "skipped" if exists else "missing"
        counted_for_continuity = False
        status_text = status_text or "SKIPPED (not run this cycle)"
    else:
        status_kind = _status_kind(status_text)
        counted_for_continuity = status_kind == "ok"

    return {
        "status": status_kind,
        "status_text": status_text,
        "data_file": data_file,
        "exists": exists,
        "updated_at": updated_at,
        "age_minutes": age_minutes,
        "counted_for_continuity": counted_for_continuity,
    }


def _build_cycle_state(cycle_type: str, cycle_started_at: str, cycle_finished_at: str, scraper_results: dict, ran_tags: set[str], merge_status: str = None, notifier_status: str = None):
    source_specs = {
        "red": ("RED", "red_products.json"),
        "yellow": ("YELLOW", "yellow_products.json"),
        "green": ("GREEN", "green_products.json"),
    }
    sources = {}
    reasons = []
    for color, (tag, data_file) in source_specs.items():
        result = scraper_results.get(tag, {})
        entry = _source_state_entry(
            tag,
            data_file,
            result.get("status_text", "SKIPPED (not run this cycle)"),
            tag in ran_tags,
        )
        sources[color] = entry
        if not entry["counted_for_continuity"]:
            reasons.append(f"{color}:{entry['status']}")

    overall_status = "healthy" if not reasons else "degraded"
    if merge_status and _status_kind(merge_status) != "ok":
        overall_status = "degraded"
        reasons.append(f"merge:{_status_kind(merge_status)}")
    if notifier_status and _status_kind(notifier_status) not in {"ok", "unknown"}:
        overall_status = "degraded"
        reasons.append(f"notifier:{_status_kind(notifier_status)}")

    return {
        "cycle_type": cycle_type,
        "cycle_started_at": cycle_started_at,
        "cycle_finished_at": cycle_finished_at,
        "continuity_safe": all(entry["counted_for_continuity"] for entry in sources.values()),
        "overall_status": overall_status,
        "reasons": reasons,
        "sources": sources,
        "merge": {"status": _status_kind(merge_status), "status_text": merge_status} if merge_status else None,
        "notifier": {"status": _status_kind(notifier_status), "status_text": notifier_status} if notifier_status else None,
    }


def _write_cycle_state(state: dict):
    with open(CYCLE_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def choose_due_job(now_monotonic: float, next_all_due_at: float, next_green_due_at: float, estimated_green_runtime: float) -> str | None:
    if now_monotonic >= next_all_due_at:
        return "all"
    if now_monotonic >= next_green_due_at:
        if now_monotonic + estimated_green_runtime >= next_all_due_at:
            return "skip_green"
        return "green"
    return None


def _prepare_proxy_connectivity(proxy_state):
    from proxy_manager import ProxyManager

    pm = ProxyManager(log_func=log)
    current_proxy = proxy_state.get("active_proxy")

    if pm.check_direct():
        if current_proxy:
            log("VkusVill reachable directly — switching Chrome back to direct mode")
            from chrome_stealth import restart_chrome_with_proxy
            restart_chrome_with_proxy(proxy=None, tag="PROXY")
            proxy_state["active_proxy"] = None
        log("VkusVill: OK (direct)")
    else:
        log("VkusVill: BLOCKED (direct connection failed)")
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
    return pm, proxy_state


def _run_scraper_set(scrapers, proxy_state):
    pm, proxy_state = _prepare_proxy_connectivity(proxy_state)

    # v1.19 REL-01..05: pre-flight VLESS bridge probe. Detect silent
    # degradation before burning 30-45 s on Chrome startup. Max 2 rotations.
    # Corrected successor to the reverted PR #25 (see .planning/phases/
    # 59-corrected-preflight-vless-probe/59-CONTEXT.md for rationale).
    probe = probe_bridge_alive(timeout=12.0)
    rotations = 0
    while not probe.ok and rotations < 2:
        log(f"  Pre-flight probe failed: {probe.reason} "
            f"(status={probe.status}, {probe.elapsed_s:.1f}s) — rotating")
        if rotations == 0:
            pm.mark_current_node_blocked("preflight_timeout")
        else:
            pm.next_proxy()
        rotations += 1
        probe = probe_bridge_alive(timeout=12.0)
    if not probe.ok:
        log(f"  Pre-flight probe still failing after {rotations} rotations "
            f"({probe.reason}) — proceeding anyway, circuit breaker will catch.")
    elif probe.cached:
        log("  Pre-flight probe: ok (cached)")
    elif rotations > 0:
        log(f"  Pre-flight probe: ok after {rotations} rotation(s) "
            f"(status={probe.status}, {probe.elapsed_s:.1f}s)")
    else:
        log(f"  Pre-flight probe: ok (status={probe.status}, {probe.elapsed_s:.1f}s)")

    scraper_results = {}
    for script, tag, data_file in scrapers:
        data_path = os.path.join(DATA_DIR, data_file)
        before_ts = os.path.getmtime(data_path) if os.path.exists(data_path) else 0

        code = run_script(script, tag)
        if code == -2 or code == 1:
            log(f"  {tag}: {'TIMEOUT' if code == -2 else 'FAILED'} — attempting kill + proxy + retry")
            _kill_all_scraper_chrome()

            proxy = pm.next_proxy()
            if proxy:
                proxy_url = f"socks5://{proxy}"
                log(f"  Restarting Chrome with proxy: {proxy_url}")
                from chrome_stealth import restart_chrome_with_proxy
                restart_chrome_with_proxy(proxy=proxy_url, tag="PROXY")
                proxy_state["active_proxy"] = proxy_url
                time.sleep(3)
                before_ts = os.path.getmtime(data_path) if os.path.exists(data_path) else 0
                code = run_script(script, f"{tag}-RETRY")
            else:
                log("  No working proxy found — skipping retry")

        file_updated = _check_file_updated(data_path, before_ts)
        status_text = _classify_scraper_status(code, file_updated)
        scraper_results[tag] = {
            "status_text": status_text,
            "code": code,
            "file_updated": file_updated,
            "data_file": data_file,
        }
        log(f"  {tag}: {status_text}")

    _kill_all_scraper_chrome()
    proxy_state["active_proxy"] = None
    return proxy_state, scraper_results


def _run_merge_and_notifier():
    log("Running merge...")
    merge_code = run_script("scrape_merge.py", "MERGE")
    merge_status = "OK (data updated)" if merge_code == 0 else f"ERROR (exit {merge_code})"

    log("Running favorite notifications...")
    notifier_code = run_script(os.path.join("backend", "notifier.py"), "NOTIF")
    notifier_status = "OK (notifications run)" if notifier_code == 0 else f"ERROR (exit {notifier_code})"
    return merge_status, notifier_status


def run_full_cycle(proxy_state):
    """Run a full scrape cycle. Returns updated proxy_state dict."""
    _kill_orphan_chromes()  # only orphans, keep main CDP Chrome alive
    log("=" * 60)
    log("=== Starting Full Scrape Cycle ===")
    log("=" * 60)
    cycle_started_at = datetime.now().isoformat(timespec="seconds")
    scrapers = [
        ("scrape_red.py", "RED", "red_products.json"),
        ("scrape_yellow.py", "YELLOW", "yellow_products.json"),
        ("scrape_green.py", "GREEN", "green_products.json"),
    ]
    proxy_state, scraper_results = _run_scraper_set(scrapers, proxy_state)
    _write_cycle_state(
        _build_cycle_state(
            "all",
            cycle_started_at,
            datetime.now().isoformat(timespec="seconds"),
            scraper_results,
            {"RED", "YELLOW", "GREEN"},
        )
    )
    merge_status, notifier_status = _run_merge_and_notifier()
    cycle_finished_at = datetime.now().isoformat(timespec="seconds")
    _write_cycle_state(
        _build_cycle_state(
            "all",
            cycle_started_at,
            cycle_finished_at,
            scraper_results,
            {"RED", "YELLOW", "GREEN"},
            merge_status=merge_status,
            notifier_status=notifier_status,
        )
    )

    log("-" * 60)
    log("Cycle Summary:")
    for tag, result in scraper_results.items():
        log(f"  {tag}: {result['status_text']}")
    log(f"  MERGE: {merge_status}")
    log(f"  NOTIF: {notifier_status}")
    log("=" * 60)

    all_failed = all(result["code"] != 0 for result in scraper_results.values())
    if all_failed:
        proxy_state["consecutive_fails"] = proxy_state.get("consecutive_fails", 0) + 1
    else:
        proxy_state["consecutive_fails"] = 0
    # Phase 60 REL-09: expose per-scraper codes so main() breaker can decide
    # on any-success reset rather than just all-clean.
    proxy_state["last_scraper_codes"] = {tag: r["code"] for tag, r in scraper_results.items()}
    return proxy_state

def run_green_only_cycle(proxy_state):
    """Run one green-only refresh cycle, then merge and notify."""
    _kill_orphan_chromes()
    log("-" * 60)
    log("=== Starting Green-Only Refresh ===")
    log("-" * 60)
    cycle_started_at = datetime.now().isoformat(timespec="seconds")
    scrapers = [
        ("scrape_green.py", "GREEN", "green_products.json"),
    ]
    proxy_state, scraper_results = _run_scraper_set(scrapers, proxy_state)
    _write_cycle_state(
        _build_cycle_state(
            "green_only",
            cycle_started_at,
            datetime.now().isoformat(timespec="seconds"),
            scraper_results,
            {"GREEN"},
        )
    )
    merge_status, notifier_status = _run_merge_and_notifier()
    cycle_finished_at = datetime.now().isoformat(timespec="seconds")
    _write_cycle_state(
        _build_cycle_state(
            "green_only",
            cycle_started_at,
            cycle_finished_at,
            scraper_results,
            {"GREEN"},
            merge_status=merge_status,
            notifier_status=notifier_status,
        )
    )
    log(f"  GREEN: {scraper_results['GREEN']['status_text']}")
    log(f"  MERGE: {merge_status}")
    log(f"  NOTIF: {notifier_status}")
    log("-" * 60)
    # Phase 60 REL-09: expose GREEN code for breaker half_open probe decision.
    proxy_state["last_scraper_codes"] = {tag: r["code"] for tag, r in scraper_results.items()}
    return proxy_state


_last_heartbeat_monotonic = time.monotonic()
_watchdog_lock = threading.Lock()


def _heartbeat():
    """Record that the main loop is still alive."""
    global _last_heartbeat_monotonic
    with _watchdog_lock:
        _last_heartbeat_monotonic = time.monotonic()


def _watchdog_loop():
    """Hard-exit if the main loop hasn't ticked for WATCHDOG_TIMEOUT_SECONDS.

    Guards against any hang that Python-level timeouts can't interrupt —
    most notably kernel-level recv() on stuck SOCKS5 sockets. systemd has
    Restart=always, so os._exit(1) brings us back in RestartSec.
    """
    while True:
        time.sleep(WATCHDOG_CHECK_INTERVAL_SECONDS)
        with _watchdog_lock:
            age = time.monotonic() - _last_heartbeat_monotonic
        if age > WATCHDOG_TIMEOUT_SECONDS:
            try:
                log(
                    f"WATCHDOG: no heartbeat for {age:.0f}s "
                    f"(limit {WATCHDOG_TIMEOUT_SECONDS}s) — forcing exit for systemd restart"
                )
            except Exception:
                pass
            os._exit(1)


def main():
    log(
        "Scheduler service started. "
        f"Full cycle target: {FULL_CYCLE_INTERVAL_SECONDS}s | "
        f"Green target: {GREEN_TARGET_INTERVAL_SECONDS}s."
    )
    log(f"Logs: {LOG_FILE}")
    log(f"Watchdog: {WATCHDOG_TIMEOUT_SECONDS}s timeout, {WATCHDOG_CHECK_INTERVAL_SECONDS}s interval")

    _heartbeat()
    watchdog_thread = threading.Thread(target=_watchdog_loop, name="scheduler-watchdog", daemon=True)
    watchdog_thread.start()

    breaker = _load_breaker_state()
    log(
        f"Loaded breaker state: {breaker.state} "
        f"(cooldown_s={breaker.cooldown_s}, fails={breaker.fails})"
    )

    proxy_state = {
        "active_proxy": None,
        "consecutive_fails": 0,
        "last_scraper_codes": {},
    }
    next_all_due_at = time.monotonic()
    next_green_due_at = next_all_due_at + GREEN_TARGET_INTERVAL_SECONDS
    estimated_green_runtime = DEFAULT_GREEN_RUNTIME_SECONDS

    while True:
        try:
            _heartbeat()
            # Check if login is active — pause scrapers to let Chrome be used for login
            if os.path.exists(PAUSE_FILE):
                log("Login in progress — pausing scrapers...")
                while os.path.exists(PAUSE_FILE):
                    _heartbeat()
                    time.sleep(5)
                log("Login finished — resuming scrapers.")
                time.sleep(3)  # Give Chrome a moment to settle

            now_monotonic = time.monotonic()
            job = choose_due_job(now_monotonic, next_all_due_at, next_green_due_at, estimated_green_runtime)

            if job is None:
                sleep_for = max(0.5, min(next_all_due_at, next_green_due_at) - now_monotonic)
                time.sleep(min(sleep_for, 5.0))
                continue

            if job == "skip_green":
                log("Skipping GREEN-only refresh to keep the next full cycle on schedule.")
                next_green_due_at = next_all_due_at + GREEN_TARGET_INTERVAL_SECONDS
                sleep_for = max(0.5, next_all_due_at - time.monotonic())
                time.sleep(min(sleep_for, 5.0))
                continue

            if job == "all":
                # Phase 60 REL-07: graduated circuit breaker drives cycle pacing.
                breaker.tick()

                if breaker.state == "open":
                    remaining = int(breaker.seconds_until_cooldown_expires())
                    if remaining % 30 == 0 or remaining < 5:
                        log(
                            f"Circuit breaker OPEN: {remaining}s until half_open "
                            f"(cooldown_s={breaker.cooldown_s})"
                        )
                    next_all_due_at = time.monotonic() + min(float(remaining), 30.0)
                    time.sleep(min(float(remaining), 5.0))
                    continue

                if breaker.state == "half_open":
                    log("Circuit breaker HALF_OPEN: running GREEN-only probe")
                    green_started = time.monotonic()
                    proxy_state = run_green_only_cycle(proxy_state)
                    green_code = proxy_state.get("last_scraper_codes", {}).get("GREEN", -1)
                    if green_code == 0:
                        breaker.record_any_success()
                        log("Circuit breaker HALF_OPEN -> CLOSED (green probe succeeded)")
                    else:
                        breaker.record_all_failed()
                        log(
                            f"Circuit breaker HALF_OPEN -> OPEN "
                            f"(cooldown_s={breaker.cooldown_s})"
                        )
                    _persist_breaker_state(breaker)
                    estimated_green_runtime = max(1.0, time.monotonic() - green_started)
                    next_green_due_at = green_started + GREEN_TARGET_INTERVAL_SECONDS
                    next_all_due_at = green_started + FULL_CYCLE_INTERVAL_SECONDS
                    continue

                # breaker.state == "closed" -> normal operation
                cycle_started = time.monotonic()
                proxy_state = run_full_cycle(proxy_state)
                last_codes = proxy_state.get("last_scraper_codes", {})
                any_success = any(code == 0 for code in last_codes.values())
                all_failed = bool(last_codes) and not any_success

                if any_success:
                    prior_state = breaker.state
                    breaker.record_any_success()
                    if prior_state != "closed" or breaker.fails > 0:
                        log("Circuit breaker reset (at least one scraper succeeded this cycle)")
                if all_failed:
                    breaker.record_all_failed()

                _persist_breaker_state(breaker)

                if breaker.state == "open":
                    log(
                        f"Circuit breaker CLOSED -> OPEN "
                        f"({breaker.fails} all-fail cycles; cooldown_s={breaker.cooldown_s})"
                    )
                    try:
                        from proxy_manager import ProxyManager
                        pm = ProxyManager(log_func=log)
                        pm.refresh_proxy_list()
                    except Exception:
                        pass
                    next_all_due_at = time.monotonic() + breaker.cooldown_s
                    next_green_due_at = next_all_due_at + GREEN_TARGET_INTERVAL_SECONDS
                else:
                    next_all_due_at = cycle_started + FULL_CYCLE_INTERVAL_SECONDS
                    next_green_due_at = cycle_started + GREEN_TARGET_INTERVAL_SECONDS
                continue

            green_started = time.monotonic()
            proxy_state = run_green_only_cycle(proxy_state)
            estimated_green_runtime = max(1.0, time.monotonic() - green_started)
            next_green_due_at = green_started + GREEN_TARGET_INTERVAL_SECONDS
        except KeyboardInterrupt:
            log("Scheduler stopped by user.")
            break
        except Exception as e:
            log(f"Unexpected error in main loop: {e}")
            time.sleep(60)


if __name__ == "__main__":
    main()

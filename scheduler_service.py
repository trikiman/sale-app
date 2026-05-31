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
from keepalive.warmup import start_warmup_loop

# Fix Windows console encoding for emoji in scraper output
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Configuration
FULL_CYCLE_INTERVAL_SECONDS = 300
GREEN_TARGET_INTERVAL_SECONDS = 60
DEFAULT_GREEN_RUNTIME_SECONDS = 60
SCRAPER_TIMEOUT = 300  # 5 minutes max per scraper

# v1.26 Phase 84.5 — robust freshness controls (target: green refresh < 5 min always)
#
# Background: full cycles run RED → YELLOW → GREEN → merge sequentially and
# take ~3-4 min. The previous skip_green guard (`now + runtime >= next_all`)
# combined with `next_green_due = cycle_started + 60` meant green-only
# intermediate runs *never* fit between full cycles — the 60s window after a
# full cycle was always smaller than the ~110s green runtime. Result:
# green file mtime gaps of 5-7 min steady state, 18-20 min during silent
# scrape stalls. User-visible "Обновлено: N мин" exceeded the 5-min limit.
#
# Phase 84.5 fixes:
#   1. GREEN_OVERSHOOT_TOLERANCE_SECONDS — let green-only push the next
#      full cycle by up to this many seconds. Trades exact 5-min full-cycle
#      cadence for green-only fitting reliably between cycles.
#   2. After full cycle: schedule next_green_due = cycle_finished + GREEN_TARGET
#      instead of cycle_started + GREEN_TARGET. This way green-only is
#      eligible ~60s after the full cycle ends, not retroactively from when
#      it started.
#   3. GREEN_STALL_THRESHOLD_SECONDS — if green file mtime exceeds this,
#      `choose_due_job` overrides the normal schedule and forces a
#      green-only run (or "all" if that's also due). Belt-and-suspenders
#      for silent scrape failures that don't write the file at all.
#
# v1.27 follow-up: STALL_RECOVERY_COOLDOWN_S — when stall recovery fires
# but the recovered green-only can't actually save the file (e.g. pool=0,
# scrape exits immediately), the file mtime stays old and the next loop
# iteration would force another stall recovery in <20s. The cooldown
# suppresses re-fires until ≥N seconds elapsed, giving each recovery
# cycle time to either succeed or hand back to the normal schedule.
GREEN_OVERSHOOT_TOLERANCE_SECONDS = 60
GREEN_STALL_THRESHOLD_SECONDS = 240  # 4 min — fires recovery before user sees the 5-min banner
STALL_RECOVERY_COOLDOWN_S = 60       # min seconds between consecutive stall-recovery overrides

# v1.27 follow-up: pool watchdog daemon. The cycle-level recovery in
# _run_scraper_set only fires when a scrape cycle is entered (every
# 60-300s). When the pool collapses MID-cycle (e.g. all admitted nodes
# fail probes in succession), the pool can sit at 0 for the full
# remainder of the cycle, causing 2-3 consecutive scrape attempts to
# error out before the next refresh. The watchdog polls pool size on
# its own clock and triggers refresh as soon as it observes pool=0 for
# ≥ POOL_DEAD_GRACE_SECONDS. Internal REFRESH_MIN_INTERVAL_S=60 in
# VlessProxyManager already throttles ensure_pool() so the watchdog
# can poll aggressively without hammering.
POOL_WATCHDOG_INTERVAL_S = 30        # poll cadence
POOL_DEAD_GRACE_SECONDS = 60         # tolerate pool=0 for this long before forcing refresh

# v1.27 follow-up #2 (2026-05-31): chronic pool-starvation pattern. Even
# with the refresh-on-dead watchdog, pools recurringly fall to zero
# because the QUARANTINE list grows faster than fresh upstream candidates
# can replenish it. After 2-4 hours of probe failures the funnel looks
# like `parsed=1300 ru=960 -uniq=205 -quarantine=200 = candidates=3` and
# none of those 3 survive — pool stuck at 0 until manual `clear_all()`.
# Same pattern hit 2026-05-17, 2026-05-22, 2026-05-29.
#
# Auto-clear policy: when pool is dead AND quarantine has grown beyond
# QUARANTINE_BURST_THRESHOLD AND has been that big for at least
# QUARANTINE_BURST_GRACE_SECONDS, fire `quarantine.clear_all()` once and
# defer the next clear by QUARANTINE_CLEAR_COOLDOWN_S so we don't flap.
# The clear releases all hosts back into the candidate pool. They'll
# re-quarantine quickly if the underlying VLESS network is genuinely
# degraded, but at least one fresh probe round gets a chance first.
QUARANTINE_BURST_THRESHOLD = 100      # min quarantine size that warrants action
QUARANTINE_BURST_GRACE_SECONDS = 300  # 5 min: pool dead + quarantine bloated this long → clear
QUARANTINE_CLEAR_COOLDOWN_S = 1800    # 30 min: don't clear more than once per window
GREEN_PRODUCTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "green_products.json")
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
    """Atomically persist breaker to disk. Non-fatal on failure.

    v1.25 OBS-09: also emits admin alert on state transition. Compares
    ``breaker.state`` against the prior persisted value; if changed,
    fires a ``breaker_transition`` alert via backend.admin_alerts.
    5-min cooldown per transition type (closed→open, open→half_open,
    half_open→closed) prevents thrash spam during flapping.
    """
    # v1.25 OBS-09: detect transition before overwriting file.
    prev_state: str | None = None
    try:
        if os.path.exists(BREAKER_STATE_FILE):
            with open(BREAKER_STATE_FILE, "r", encoding="utf-8") as fh:
                prev = json.load(fh)
                prev_state = prev.get("state")
    except (OSError, json.JSONDecodeError):
        prev_state = None

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
        return  # don't alert if we couldn't even save

    # v1.25 OBS-09: admin alert on state transition.
    if prev_state and prev_state != breaker.state:
        try:
            from backend import admin_alerts
            admin_alerts.send_admin_alert(
                "breaker_transition",
                (
                    f"Breaker state changed: <b>{prev_state}</b> → <b>{breaker.state}</b>\n"
                    f"Fails: {breaker.fails}\n"
                    f"Cooldown: {breaker.cooldown_s}s"
                ),
                cooldown_s=300,  # 5-min cooldown per transition (same type may flap)
                extra={
                    "prev_state": prev_state,
                    "new_state": breaker.state,
                    "fails": breaker.fails,
                    "cooldown_s": breaker.cooldown_s,
                },
            )
        except Exception:  # noqa: BLE001
            pass  # admin alerts must never break breaker state management


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


def _green_file_age_seconds() -> float | None:
    """v1.26 Phase 84.5: return age (in seconds) of green_products.json.

    Returns ``None`` if the file is missing — callers must treat that as
    "no information available" rather than "infinitely stale" because a
    missing file is the fresh-deploy scenario, not a refresh failure.
    """
    try:
        return time.time() - os.path.getmtime(GREEN_PRODUCTS_PATH)
    except OSError:
        return None


def choose_due_job(
    now_monotonic: float,
    next_all_due_at: float,
    next_green_due_at: float,
    estimated_green_runtime: float,
    *,
    green_age_seconds: float | None = None,
) -> str | None:
    """Pick the next scheduler job. Returns ``"all"``, ``"green"``, ``"skip_green"``, or ``None``.

    v1.26 Phase 84.5 changes:
      - New ``green_age_seconds`` kwarg: when set and exceeding
        ``GREEN_STALL_THRESHOLD_SECONDS``, the function forces a green
        refresh (or ``"all"`` if that's also due). Belt-and-suspenders
        for silent scrape failures.
      - Loosened ``skip_green`` guard: green-only is allowed to run if
        its estimated runtime would push ``next_all_due_at`` by no more
        than ``GREEN_OVERSHOOT_TOLERANCE_SECONDS``. The previous strict
        check (``>= next_all_due_at``) prevented green-only from ever
        fitting between full cycles, which caused the user-reported
        5-19 min staleness gap on EC2.
    """
    # Stall recovery: green file is way past the user-visible
    # staleness threshold. Force a fresh green write regardless of the
    # normal schedule. If a full cycle is also due we prefer that
    # because it includes green AND refreshes red/yellow.
    if green_age_seconds is not None and green_age_seconds > GREEN_STALL_THRESHOLD_SECONDS:
        if now_monotonic >= next_all_due_at:
            return "all"
        return "green"

    if now_monotonic >= next_all_due_at:
        return "all"
    if now_monotonic >= next_green_due_at:
        # Phase 84.5: allow green-only to push next_all by up to
        # GREEN_OVERSHOOT_TOLERANCE_SECONDS. The strict bound caused
        # skip_green to fire on every cycle; full cycle drift of ≤60s
        # is acceptable in exchange for keeping green refresh tight.
        if now_monotonic + estimated_green_runtime > next_all_due_at + GREEN_OVERSHOOT_TOLERANCE_SECONDS:
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


# v1.24 REL-19: scheduler graceful degrade event ledger
_SCHEDULER_EVENTS_PATH = os.path.join(DATA_DIR, "scheduler_events.jsonl")


def _emit_scheduler_event(event_type: str, **fields) -> None:
    """Append a JSONL event. Best-effort — never raises."""
    try:
        entry = {
            "ts": round(time.time(), 3),
            "event": event_type,
            **fields,
        }
        os.makedirs(os.path.dirname(_SCHEDULER_EVENTS_PATH), exist_ok=True)
        with open(_SCHEDULER_EVENTS_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, separators=(",", ":"), ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001
        pass


def _is_pool_dead() -> bool:
    """Cheap check — read the shared vless_pool.json directly.

    Returns True if the VLESS pool has zero nodes. Using the raw file
    read avoids spinning up a VlessProxyManager instance (which would
    try to start xray), so this is safe to call before every scrape.
    """
    try:
        pool_path = os.path.join(DATA_DIR, "vless_pool.json")
        if not os.path.exists(pool_path):
            return True
        with open(pool_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return len(data.get("nodes", [])) == 0
    except Exception:  # noqa: BLE001 — broken file → treat as dead
        return True


def _pool_watchdog_loop(stop_event: "threading.Event") -> None:
    """v1.27 daemon thread that aggressively refreshes the VLESS pool
    whenever it observes pool=0 for ≥ POOL_DEAD_GRACE_SECONDS.

    Decoupled from scrape cycles so mid-cycle pool collapses (which
    happen when all admitted nodes fail probes within seconds of each
    other) get repaired before the next cycle even starts. The internal
    REFRESH_MIN_INTERVAL_S=60s throttle in VlessProxyManager.ensure_pool
    prevents this from hammering the upstream subscription source.

    Runs forever until stop_event is set. Logs every state transition
    and every refresh attempt so journal forensics stays clear.
    """
    pool_dead_since: float | None = None
    last_refresh_attempt: float = 0.0
    # v1.27 follow-up #2: track when quarantine first crossed the burst
    # threshold while pool was dead. Auto-clear fires when this state
    # has persisted for QUARANTINE_BURST_GRACE_SECONDS. Cooldown prevents
    # repeated clears in case the network is genuinely down (clearing won't
    # help, just adds churn).
    quarantine_bloated_since: float | None = None
    last_quarantine_clear: float = 0.0
    log("[pool-watchdog] Started — polling every "
        f"{POOL_WATCHDOG_INTERVAL_S}s, refresh after "
        f"{POOL_DEAD_GRACE_SECONDS}s dead.")
    while not stop_event.is_set():
        try:
            now = time.monotonic()
            if _is_pool_dead():
                if pool_dead_since is None:
                    pool_dead_since = now
                    log("[pool-watchdog] Pool observed dead — starting grace timer")
                dead_for = now - pool_dead_since
                if (
                    dead_for >= POOL_DEAD_GRACE_SECONDS
                    and (now - last_refresh_attempt) >= POOL_DEAD_GRACE_SECONDS
                ):
                    log(
                        f"[pool-watchdog] Pool dead for {dead_for:.0f}s — "
                        "triggering ensure_pool()"
                    )
                    last_refresh_attempt = now
                    try:
                        from vless.manager import VlessProxyManager
                        pm = VlessProxyManager(log_func=log, register_atexit=False)
                        recovered = pm.ensure_pool()
                        log(
                            f"[pool-watchdog] ensure_pool() returned "
                            f"{recovered} nodes"
                        )
                        if recovered > 0:
                            pool_dead_since = None  # reset grace timer
                    except Exception as exc:  # noqa: BLE001
                        log(f"[pool-watchdog] ensure_pool() failed: {exc!r}")

                # v1.27 follow-up #2: auto-clear quarantine if it's
                # crowding out fresh candidates. Only when pool is also
                # dead — a healthy pool with big quarantine is fine.
                try:
                    from vless import quarantine as _q
                    q_count = _q.snapshot().get("count", 0)
                    if q_count >= QUARANTINE_BURST_THRESHOLD:
                        if quarantine_bloated_since is None:
                            quarantine_bloated_since = now
                            log(
                                f"[pool-watchdog] Quarantine bloat detected "
                                f"({q_count} hosts) — starting bloat timer"
                            )
                        bloated_for = now - quarantine_bloated_since
                        cooldown_elapsed = now - last_quarantine_clear
                        if (
                            bloated_for >= QUARANTINE_BURST_GRACE_SECONDS
                            and cooldown_elapsed >= QUARANTINE_CLEAR_COOLDOWN_S
                        ):
                            log(
                                f"[pool-watchdog] Pool dead {dead_for:.0f}s + "
                                f"quarantine={q_count} bloated {bloated_for:.0f}s "
                                "— firing quarantine.clear_all()"
                            )
                            try:
                                _q.clear_all()
                                last_quarantine_clear = now
                                quarantine_bloated_since = None
                                log("[pool-watchdog] quarantine cleared OK")
                            except Exception as exc:  # noqa: BLE001
                                log(f"[pool-watchdog] quarantine.clear_all() failed: {exc!r}")
                    else:
                        # Quarantine shrank below threshold (ttl expiry or
                        # external clear) — reset the bloat timer.
                        quarantine_bloated_since = None
                except Exception as exc:  # noqa: BLE001
                    log(f"[pool-watchdog] quarantine check failed: {exc!r}")
            else:
                if pool_dead_since is not None:
                    log(
                        f"[pool-watchdog] Pool recovered after "
                        f"{now - pool_dead_since:.0f}s dead"
                    )
                    pool_dead_since = None
                # Pool healthy — quarantine bloat doesn't matter, reset timer.
                quarantine_bloated_since = None
        except Exception as exc:  # noqa: BLE001 — never let watchdog die
            log(f"[pool-watchdog] loop error: {exc!r}")
        # Sleep in 1s slices so stop_event is responsive on shutdown.
        for _ in range(POOL_WATCHDOG_INTERVAL_S):
            if stop_event.is_set():
                return
            time.sleep(1)
    log("[pool-watchdog] Stopped (stop_event set)")


def _run_scraper_set(scrapers, proxy_state):
    # v1.24 REL-19 + v1.25 hotfix: graceful degrade — if the VLESS pool is
    # empty for 2+ consecutive cycles, skip the expensive Chrome startup
    # (60-90s per scraper that will fail) but ALWAYS trigger pool refresh
    # so recovery continues. The 2026-05-13 23:04 → 01:13 incident proved
    # that skipping-without-refreshing is a terminal state: nothing else
    # in the scheduler path calls ensure_pool(), so if we don't do it here,
    # the pool stays at 0 forever.
    if _is_pool_dead():
        proxy_state["consecutive_pool_dead_cycles"] = (
            proxy_state.get("consecutive_pool_dead_cycles", 0) + 1
        )
        consecutive = proxy_state["consecutive_pool_dead_cycles"]

        # CRITICAL: always attempt pool refresh on every dead cycle, even
        # when we're skipping scrape. This is the only path that calls
        # ensure_pool() from the scheduler; without it, graceful-degrade
        # becomes a terminal "stuck" state.
        try:
            from vless.manager import VlessProxyManager
            log(f"Pool dead (cycle {consecutive}) — triggering refresh before deciding skip-or-run")
            _refresh_pm = VlessProxyManager(log_func=log, register_atexit=False)
            refreshed_count = _refresh_pm.ensure_pool()
            log(f"  ensure_pool() returned {refreshed_count} nodes")
            # Re-check after refresh — if pool came back, fall through to
            # normal scrape path without the skip.
            if not _is_pool_dead():
                log(f"  Pool recovered to {refreshed_count} — proceeding with scrape")
                proxy_state["consecutive_pool_dead_cycles"] = 0
                _emit_scheduler_event(
                    "scheduler_pool_recovered",
                    consecutive_dead_cycles=consecutive,
                    recovered_size=refreshed_count,
                )
                # v1.25 OBS-08: recovery notification. Only fires if we
                # were previously in a significant outage (≥ 4 cycles ≈
                # 12 min) — avoids spamming on every 1-cycle blip.
                if consecutive >= 4:
                    try:
                        from backend import admin_alerts
                        admin_alerts.send_admin_alert(
                            "scheduler_pool_recovered",
                            (
                                f"Pool recovered ✅\n\n"
                                f"Dead cycles: {consecutive}\n"
                                f"Recovered size: {refreshed_count}"
                            ),
                            extra={
                                "consecutive_dead_cycles": consecutive,
                                "recovered_size": refreshed_count,
                            },
                        )
                    except Exception:  # noqa: BLE001
                        pass
                # Fall through to normal scrape path.
            else:
                # Still dead after refresh attempt — now honor skip.
                if consecutive >= 2:
                    log(
                        f"Pool still dead after refresh ({consecutive} cycles) — "
                        f"skipping scrape (REL-19). Next cycle will refresh again."
                    )
                    _emit_scheduler_event(
                        "scheduler_pool_dead",
                        consecutive_dead_cycles=consecutive,
                        scrapers_skipped=[tag for _, tag, _ in scrapers],
                    )
                    # v1.25 OBS-08: pool-dead alert. 4+ consecutive cycles
                    # ≈ 12+ min of no data. 30-min cooldown prevents
                    # spam during extended outages. First alert fires
                    # fast; subsequent within cooldown are skipped.
                    if consecutive >= 4:
                        try:
                            from backend import admin_alerts
                            admin_alerts.send_admin_alert(
                                "pool_dead",
                                (
                                    f"VLESS pool dead 🚨\n\n"
                                    f"Dead cycles: {consecutive} (~{consecutive * 3} min)\n"
                                    f"Last refresh returned 0 nodes — no recovery.\n"
                                    f"Users see cached data with staleAll banner."
                                ),
                                extra={
                                    "consecutive_dead_cycles": consecutive,
                                },
                            )
                        except Exception:  # noqa: BLE001
                            pass
                    return proxy_state, {
                        tag: {
                            "status_text": "SKIPPED (pool dead)",
                            "code": 0,
                            "file_updated": False,
                            "data_file": data_file,
                        }
                        for _, tag, data_file in scrapers
                    }
        except Exception as e:  # noqa: BLE001
            log(f"  Pool refresh attempt failed: {type(e).__name__}: {e}")
            # Continue to skip if we can't even refresh.
            if consecutive >= 2:
                _emit_scheduler_event(
                    "scheduler_pool_dead",
                    consecutive_dead_cycles=consecutive,
                    scrapers_skipped=[tag for _, tag, _ in scrapers],
                    refresh_error=f"{type(e).__name__}: {str(e)[:200]}",
                )
                return proxy_state, {
                    tag: {
                        "status_text": "SKIPPED (pool dead)",
                        "code": 0,
                        "file_updated": False,
                        "data_file": data_file,
                    }
                    for _, tag, data_file in scrapers
                }
    else:
        # Pool is alive (size > 0) — reset consecutive-dead counter.
        proxy_state["consecutive_pool_dead_cycles"] = 0

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

    # v1.20 PERF-03/04/05: sessid keep-alive + on-app-open warmup daemon.
    # See .planning/phases/62-sessid-keepalive-warmup/62-CONTEXT.md for
    # decisions D1-D4. Thread respects stop_event; scheduler watchdog covers
    # process-level death. Module handles its own retries inside the loop.
    _keepalive_stop_event = threading.Event()
    keepalive_thread = threading.Thread(
        target=start_warmup_loop,
        args=(_keepalive_stop_event,),
        name="scheduler-keepalive",
        daemon=True,
    )
    keepalive_thread.start()

    # v1.21 REL-13: VLESS pool self-healing re-probe daemon. Every 10 min
    # iterates admitted hosts, re-probes each through the running bridge
    # (proxy=None), and routes failures into the existing 4h VkusVill
    # cooldown. See .planning/phases/67-admitted-node-self-healing-loop/
    # 67-CONTEXT.md §SPEC Lock. The scheduler uses LOCAL ProxyManager
    # instances inside cycle functions (no module-level singleton), so the
    # daemon constructs its own instance — the pool file on disk is the
    # source of truth and both instances read it.
    from keepalive.reprobe import start_reprobe_loop
    from proxy_manager import ProxyManager as _ReprobePM
    _reprobe_proxy_manager = _ReprobePM(log_func=log)
    _reprobe_stop_event = threading.Event()
    reprobe_thread = threading.Thread(
        target=start_reprobe_loop,
        args=(_reprobe_stop_event, _reprobe_proxy_manager),
        name="scheduler-reprobe",
        daemon=True,
    )
    reprobe_thread.start()

    # v1.27: aggressive pool-refresh watchdog. Decoupled from scrape
    # cycles — fires when pool has been dead for POOL_DEAD_GRACE_SECONDS
    # regardless of cycle phase. Same shutdown protocol as keepalive
    # (stop_event + daemon=True).
    _pool_watchdog_stop_event = threading.Event()
    pool_watchdog_thread = threading.Thread(
        target=_pool_watchdog_loop,
        args=(_pool_watchdog_stop_event,),
        name="scheduler-pool-watchdog",
        daemon=True,
    )
    pool_watchdog_thread.start()

    breaker = _load_breaker_state()
    log(
        f"Loaded breaker state: {breaker.state} "
        f"(cooldown_s={breaker.cooldown_s}, fails={breaker.fails})"
    )
    # Phase 60 REL-10: persist immediately on startup so external monitors
    # (verify_v1.19.sh 60-F, future /api/health/deep) can always read a
    # current state even on a fresh boot before the first cycle completes.
    _persist_breaker_state(breaker)

    proxy_state = {
        "active_proxy": None,
        "consecutive_fails": 0,
        "last_scraper_codes": {},
    }
    next_all_due_at = time.monotonic()
    next_green_due_at = next_all_due_at + GREEN_TARGET_INTERVAL_SECONDS
    estimated_green_runtime = DEFAULT_GREEN_RUNTIME_SECONDS
    # v1.27: monotonic timestamp of the last stall-recovery override. Init
    # to negative infinity so the first stall recovery isn't suppressed.
    last_stall_recovery_monotonic = float("-inf")

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
            green_age = _green_file_age_seconds()
            # v1.27: suppress stall recovery for STALL_RECOVERY_COOLDOWN_S after
            # the last forced override so we don't spin every 20s when pool=0
            # (recovery fires green → green can't save because no proxy →
            # mtime stays old → recovery fires again). Cooldown gives each
            # attempt time to either succeed or hand back to the normal schedule.
            stall_active = (
                green_age is not None
                and green_age > GREEN_STALL_THRESHOLD_SECONDS
                and (now_monotonic - last_stall_recovery_monotonic) > STALL_RECOVERY_COOLDOWN_S
            )
            job = choose_due_job(
                now_monotonic,
                next_all_due_at,
                next_green_due_at,
                estimated_green_runtime,
                green_age_seconds=green_age if stall_active else None,
            )

            # v1.26 Phase 84.5: surface stall-recovery activations in the
            # journal so operators can spot when something silently broke
            # the normal cadence (vs. a planned green-only run).
            if stall_active and job in ("all", "green"):
                log(
                    f"Green-stall recovery: green_products.json is {green_age:.0f}s old "
                    f"(threshold {GREEN_STALL_THRESHOLD_SECONDS}s) — forcing job={job}"
                )
                last_stall_recovery_monotonic = now_monotonic

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
                    # v1.26 Phase 84.5: schedule next green-only based on
                    # cycle_finished, not cycle_started. Otherwise, the
                    # full cycle ends at ~T+240s and `cycle_started + 60s`
                    # is already 180s overdue — the skip_green guard fires
                    # immediately and green-only never gets a turn until
                    # the next full cycle.
                    cycle_finished_monotonic = time.monotonic()
                    next_all_due_at = cycle_started + FULL_CYCLE_INTERVAL_SECONDS
                    next_green_due_at = cycle_finished_monotonic + GREEN_TARGET_INTERVAL_SECONDS
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

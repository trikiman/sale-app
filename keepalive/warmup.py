"""VkusVill sessid keep-alive daemon + on-app-open warmup nudge processor.

Spawned from scheduler_service.main() as a daemon thread. Keeps every linked
user's sessid warm so the cart-add hot path never pays the ~1.5 s inline
refresh tax. Nudge dispatch budget: <=500 ms (PERF-04).

Design decisions (see .planning/phases/62-sessid-keepalive-warmup/62-CONTEXT.md):

- D1: warm ALL linked users every 20 min (no activity filter).
- D2: silent log + JSONL on failure, NO inline stale mark, NO Telegram alerts.
- D3: daemon thread inside scheduler_service.py; this module is the callee.
- D4: cart-add cancels in-flight warmup via CART_ADD_ACTIVE flag; warmup
  checks the flag before AND after sending bytes.

Anti-spam: _LAST_WARMUP_AT[user_id_hash] = monotonic_ts. <=1 warmup per user
per 15 min across scheduler cycles + on-app-open nudges combined.

JSONL schema (one line per outcome, newline-terminated, 8 keys total):
  {"timestamp_iso": "2026-05-05T12:34:56+00:00",
   "user_id_hash": "a1b2c3d4e5f6",
   "trigger": "scheduler" | "app_open",
   "endpoint": "GET /personal/",
   "success": true,
   "outcome": "ok" | "timeout" | "http_error" | "skipped_unhealthy"
              | "skipped_recent" | "cancelled_by_cart_add" | "raced",
   "latency_ms": 412,
   "sessid_changed": false}

`endpoint` is the HTTP method + path used for the warmup hit (currently
"GET /personal/"). `success` is a boolean derived from outcome:
  success == (outcome in {"ok", "raced"}).
Distinct from outcome so downstream metrics can do success-rate aggregation
without joining on the enum (ROADMAP #3 + CONTEXT §SPEC Lock).

Tests reach into module internals (_STATE_LOCK, _LAST_WARMUP_AT, _run_cycle,
_emit_event, _warmup_single_user). This is intentional test-only access.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import queue
import re
import sys
import threading
import time
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

# --- Tuning constants (LOCKED by 62-CONTEXT.md) -----------------------------
CYCLE_INTERVAL_S = 20 * 60
ANTI_SPAM_WINDOW_S = 15 * 60
# PERF-04: <=500 ms from nudge enqueue to warmup kickoff. queue.Queue.get(timeout=0.25)
# polls quickly without a busy-spin (OS-blocking wait w/ timeout, ~0 CPU between wakeups).
NUDGE_POLL_INTERVAL_S = 0.25
WARMUP_P95_BUDGET_S = 3.0
BOOT_GRACE_S = 60.0
JSONL_MAX_BYTES = 10 * 1024 * 1024
# How long CART_ADD_ACTIVE flag is considered fresh. Cart-add p95 today is
# ~10 s; we give 15 s head-room. Older entries are treated as stale and
# ignored (prevents permanent cancellation if flag is leaked).
CART_ADD_FLAG_FRESH_S = 15.0

# CONTEXT §Locked Defaults: warmup uses its own tight timeout (5s connect / 5s
# read / 3s write / 3s pool) — NOT SESSID_REFRESH_TIMEOUT (10s/10s) which would
# blow past PERF-05's 3 s p95 budget. Module-local so cart hot path stays
# unchanged.
WARMUP_TIMEOUT = httpx.Timeout(connect=5.0, read=5.0, write=3.0, pool=3.0)
WARMUP_URL = "https://vkusvill.ru/personal/"
WARMUP_ENDPOINT_LABEL = "GET /personal/"
WARMUP_PROXY = "socks5h://127.0.0.1:10808"
WARMUP_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
USER_COOKIES_DIR = os.path.join(DATA_DIR, "user_cookies")
PHONE_MAP_PATH = os.path.join(DATA_DIR, "auth", "user_phone_map.json")
PHONE_AUTH_DIR = os.path.join(DATA_DIR, "auth")
WARMUP_JSONL_PATH = os.path.join(DATA_DIR, "warmup_events.jsonl")

# --- Module-level state (thread-safe via _STATE_LOCK) -----------------------
_STATE_LOCK = threading.Lock()
_LAST_WARMUP_AT: "dict[str, float]" = {}
CART_ADD_ACTIVE: "dict[str, float]" = {}
NUDGE_QUEUE: "queue.Queue[str]" = queue.Queue(maxsize=256)


def hash_user_id(user_id: str) -> str:
    """12-char hex prefix of sha256 - matches Phase 66 cart_events.jsonl convention.

    Public (no leading underscore) because 62-02's backend nudge handlers
    and cart-add flag setter import it across module boundaries.
    """
    return hashlib.sha256(str(user_id).encode("utf-8")).hexdigest()[:12]


def _collect_linked_users() -> "list[tuple[str, str]]":
    """Return list of (user_id_hash, cookies_path) pairs.

    Union of:
      - data/user_cookies/{telegram_id}.json  (bot/auth.py:30-35 convention)
      - data/auth/user_phone_map.json values  (phone-mapped users via
        data/auth/{phone}/cookies.json)

    Dedupes by resolved cookies_path (canonical absolute path).

    D1 override: CONTEXT.md supersedes ROADMAP "recent-activity" gating —
    warm ALL linked users every cycle. Family-scale (~5 users) makes
    activity filtering over-engineering. See 62-CONTEXT.md §D1.
    """
    pairs: "list[tuple[str, str]]" = []
    seen_paths: "set[str]" = set()

    # 1) telegram-keyed cookies under data/user_cookies/{id}.json
    try:
        if os.path.isdir(USER_COOKIES_DIR):
            for fname in os.listdir(USER_COOKIES_DIR):
                if not fname.endswith(".json"):
                    continue
                # Skip the *_browser.json variants (not session-bearing)
                if fname.endswith("_browser.json"):
                    continue
                uid = fname[:-5]
                if not uid:
                    continue
                p = os.path.join(USER_COOKIES_DIR, fname)
                try:
                    canon = os.path.realpath(p)
                except OSError:
                    canon = p
                if canon in seen_paths:
                    continue
                seen_paths.add(canon)
                pairs.append((hash_user_id(uid), p))
    except Exception:  # noqa: BLE001
        logger.debug("keepalive: scanning user_cookies failed", exc_info=True)

    # 2) phone-keyed cookies via user_phone_map.json
    try:
        if os.path.exists(PHONE_MAP_PATH):
            with open(PHONE_MAP_PATH, "r", encoding="utf-8") as fh:
                mapping = json.load(fh) or {}
            # One cookies.json per phone; many user_ids may map to the same
            # phone, but we only want to warm the underlying session once.
            phones_handled: "set[str]" = set()
            for user_id, phone in mapping.items():
                if not user_id or not phone:
                    continue
                phone_s = str(phone)
                if phone_s in phones_handled:
                    continue
                phones_handled.add(phone_s)
                p = os.path.join(PHONE_AUTH_DIR, phone_s, "cookies.json")
                if not os.path.exists(p):
                    continue
                try:
                    canon = os.path.realpath(p)
                except OSError:
                    canon = p
                if canon in seen_paths:
                    continue
                seen_paths.add(canon)
                # Hash the phone (stable identifier; matches the 62-D smoke
                # check in scripts/verify_v1.20.sh which hashes the mapping
                # key, but for phone-mapped users we prefer the phone as
                # the canonical session identifier).
                pairs.append((hash_user_id(phone_s), p))
    except Exception:  # noqa: BLE001
        logger.debug("keepalive: scanning phone_map failed", exc_info=True)

    return pairs


def _pool_is_healthy() -> bool:
    """Gate: pool_snapshot() + xray listening + breaker closed.

    Imported lazily to avoid import-time circular with scheduler_service
    (which imports keepalive.warmup at top).

    Healthy = all of:
      - pool_snapshot has size > 0
      - quarantined_count < max(1, size // 2)
      - xray listening on the configured bridge port
      - breaker.state != "open"

    On any exception (e.g. VLESS stack not yet booted), returns False so
    we don't hammer VkusVill from a broken bridge.
    """
    try:
        from vless.manager import VlessProxyManager  # lazy
    except Exception:  # noqa: BLE001
        logger.debug("keepalive: cannot import vless.manager", exc_info=True)
        return False

    try:
        pm = VlessProxyManager(log_func=lambda _m: None)
        snap = pm.pool_snapshot()
    except Exception:  # noqa: BLE001
        logger.debug("keepalive: pool_snapshot failed", exc_info=True)
        return False

    size = int(snap.get("size") or 0)
    if size <= 0:
        return False
    quarantined = int(snap.get("quarantined_count") or 0)
    if quarantined >= max(1, size // 2):
        return False

    try:
        if not pm._external_xray_listening():  # noqa: SLF001
            # If our own xray process is running, that also counts. Check
            # in-proc xray as a secondary signal.
            in_proc = getattr(pm, "_xray", None)
            if in_proc is None or not in_proc.is_running():
                return False
    except Exception:  # noqa: BLE001
        logger.debug("keepalive: xray listen probe failed", exc_info=True)
        return False

    # Breaker check - lazy import to avoid import-cycle
    try:
        import scheduler_service  # lazy

        breaker = scheduler_service._load_breaker_state()  # noqa: SLF001
        state = getattr(breaker, "state", None)
        if state == "open":
            return False
    except Exception:  # noqa: BLE001
        logger.debug("keepalive: breaker probe failed", exc_info=True)
        # Breaker inaccessible is not automatically unhealthy; we trust
        # the pool+xray signals above. Proceed.

    return True


def _should_skip_for_anti_spam(user_id_hash: str, now_monotonic: float) -> bool:
    with _STATE_LOCK:
        last = _LAST_WARMUP_AT.get(user_id_hash)
    return last is not None and (now_monotonic - last) < ANTI_SPAM_WINDOW_S


def _cart_add_is_active(user_id_hash: str, now_monotonic: float) -> bool:
    """Return True if a fresh cart-add is in flight for this user."""
    with _STATE_LOCK:
        ts = CART_ADD_ACTIVE.get(user_id_hash)
    if ts is None:
        return False
    return (now_monotonic - ts) < CART_ADD_FLAG_FRESH_S


def _emit_event(payload: dict) -> None:
    """Append one JSONL line. Rotate to .1 if > 10 MB. Never raises.

    Uses fcntl.flock on POSIX for line atomicity across processes (R2 in
    62-CONTEXT.md). On Windows, O_APPEND + single-shot write is enough
    for local dev (single-process testing); production runs POSIX.
    """
    try:
        os.makedirs(os.path.dirname(WARMUP_JSONL_PATH), exist_ok=True)
        # Rotation check first (pre-write): rotate if current file is at/over
        # the cap. Atomic replace to .1 (older .1 is overwritten).
        try:
            if os.path.exists(WARMUP_JSONL_PATH):
                if os.path.getsize(WARMUP_JSONL_PATH) > JSONL_MAX_BYTES:
                    rotated = WARMUP_JSONL_PATH + ".1"
                    try:
                        # os.replace works cross-platform; overwrites existing .1
                        os.replace(WARMUP_JSONL_PATH, rotated)
                    except OSError:
                        logger.debug("keepalive: rotate failed", exc_info=True)
        except OSError:
            logger.debug("keepalive: rotation size probe failed", exc_info=True)

        line = json.dumps(payload, ensure_ascii=False, default=str) + "\n"
        data = line.encode("utf-8")

        if sys.platform != "win32":
            import fcntl  # POSIX only

            fd = os.open(
                WARMUP_JSONL_PATH,
                os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                0o644,
            )
            try:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX)
                except OSError:
                    pass
                try:
                    os.write(fd, data)
                finally:
                    try:
                        fcntl.flock(fd, fcntl.LOCK_UN)
                    except OSError:
                        pass
            finally:
                os.close(fd)
        else:
            # Windows fallback: O_APPEND on stock filesystems is atomic
            # for writes below PIPE_BUF-ish sizes. Sufficient for dev/tests.
            with open(WARMUP_JSONL_PATH, "ab") as fh:
                fh.write(data)
    except Exception:  # noqa: BLE001 — never raise
        logger.warning("keepalive: _emit_event failed", exc_info=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _outcome_success(outcome: str) -> bool:
    # success == (outcome in {"ok", "raced"})  -- see module docstring
    return outcome in ("ok", "raced")


def _load_cookie_doc(cookies_path: str) -> "dict | None":
    try:
        with open(cookies_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(data, dict):
        return data
    # list-format cookies (no metadata wrapper) — treat as missing so we
    # skip rather than corrupt.
    return None


def _cookie_header_from_doc(doc: dict) -> str:
    cookies_list = doc.get("cookies") or []
    parts = []
    for c in cookies_list:
        if not isinstance(c, dict):
            continue
        name = c.get("name")
        value = c.get("value")
        if name and value is not None:
            parts.append(f"{name}={value}")
    return "; ".join(parts)


_SESSID_INPUT_RE = re.compile(r"name=['\"]sessid['\"].*?value=['\"]([^'\"]+)['\"]")
_USER_ID_INPUT_RE = re.compile(r"id=[\"']lk-user-id[\"'].*?value=[\"'](\d+)[\"']")
_USER_ID_JSON_RE = re.compile(r'"USER_ID"\s*:\s*"(\d+)"')


def _parse_sessid(body: str) -> "str | None":
    m = _SESSID_INPUT_RE.search(body)
    return m.group(1) if m else None


def _parse_user_id(body: str) -> "int | None":
    m = _USER_ID_INPUT_RE.search(body)
    if not m:
        m = _USER_ID_JSON_RE.search(body)
    if not m:
        return None
    try:
        return int(m.group(1))
    except (TypeError, ValueError):
        return None


def _persist_cookie_doc(cookies_path: str, doc: dict, *, new_sessid: "str | None",
                        new_user_id: "int | None") -> None:
    """Atomic-ish rewrite of cookies.json preserving cookie list."""
    try:
        if new_sessid:
            doc["sessid"] = new_sessid
        if new_user_id:
            doc["user_id"] = new_user_id
        doc["sessid_ts"] = time.time()
        tmp = cookies_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, cookies_path)
    except OSError:
        logger.warning("keepalive: persist cookies failed", exc_info=True)


def _warmup_single_user(user_id_hash: str, cookies_path: str, trigger: str,
                        stop_event: threading.Event) -> None:
    """Warm one user. Checks CART_ADD_ACTIVE flag before AND after (D4).

    Emits exactly one JSONL event. Never raises.
    """
    t_start = time.monotonic()

    # D4 pre-check: if a cart-add is in flight, skip entirely.
    if _cart_add_is_active(user_id_hash, t_start):
        _emit_event({
            "timestamp_iso": _now_iso(),
            "user_id_hash": user_id_hash,
            "trigger": trigger,
            "endpoint": WARMUP_ENDPOINT_LABEL,
            "success": False,
            "outcome": "cancelled_by_cart_add",
            "latency_ms": 0,
            "sessid_changed": False,
        })
        with _STATE_LOCK:
            _LAST_WARMUP_AT[user_id_hash] = t_start
        return

    doc = _load_cookie_doc(cookies_path)
    if doc is None:
        _emit_event({
            "timestamp_iso": _now_iso(),
            "user_id_hash": user_id_hash,
            "trigger": trigger,
            "endpoint": WARMUP_ENDPOINT_LABEL,
            "success": False,
            "outcome": "http_error",
            "latency_ms": int((time.monotonic() - t_start) * 1000),
            "sessid_changed": False,
        })
        with _STATE_LOCK:
            _LAST_WARMUP_AT[user_id_hash] = t_start
        return

    old_sessid = str(doc.get("sessid") or "")
    cookie_header = _cookie_header_from_doc(doc)

    if stop_event.is_set():
        return

    outcome = "http_error"
    new_sessid: "str | None" = None
    new_user_id: "int | None" = None

    try:
        resp = httpx.get(
            WARMUP_URL,
            timeout=WARMUP_TIMEOUT,
            proxy=WARMUP_PROXY,
            headers={
                "User-Agent": WARMUP_USER_AGENT,
                "Cookie": cookie_header,
            },
            follow_redirects=False,
        )
        if resp.status_code == 200:
            body = resp.text or ""
            new_sessid = _parse_sessid(body) or old_sessid or None
            new_user_id = _parse_user_id(body)
            outcome = "ok"
        else:
            outcome = "http_error"
    except httpx.TimeoutException:
        outcome = "timeout"
    except httpx.HTTPError:
        outcome = "http_error"
    except Exception:  # noqa: BLE001
        logger.debug("keepalive: unexpected warmup error", exc_info=True)
        outcome = "http_error"

    # D4 post-check: if cart-add started mid-request, mark raced.
    if _cart_add_is_active(user_id_hash, time.monotonic()):
        outcome = "raced"

    sessid_changed = bool(
        outcome in ("ok", "raced")
        and new_sessid is not None
        and old_sessid
        and new_sessid != old_sessid
    )

    if outcome == "ok" and new_sessid:
        _persist_cookie_doc(cookies_path, doc, new_sessid=new_sessid,
                            new_user_id=new_user_id)

    latency_ms = int((time.monotonic() - t_start) * 1000)

    _emit_event({
        "timestamp_iso": _now_iso(),
        "user_id_hash": user_id_hash,
        "trigger": trigger,
        "endpoint": WARMUP_ENDPOINT_LABEL,
        "success": _outcome_success(outcome),
        "outcome": outcome,
        "latency_ms": latency_ms,
        "sessid_changed": sessid_changed,
    })

    # Anti-spam: record timestamp regardless of outcome (prevents retry spam).
    with _STATE_LOCK:
        _LAST_WARMUP_AT[user_id_hash] = t_start


def _run_cycle(stop_event: threading.Event) -> None:
    """One warmup cycle. Gate check, iterate users, emit JSONL."""
    users = _collect_linked_users()
    if not users:
        return

    if not _pool_is_healthy():
        ts = _now_iso()
        for user_id_hash, _ in users:
            _emit_event({
                "timestamp_iso": ts,
                "user_id_hash": user_id_hash,
                "trigger": "scheduler",
                "endpoint": WARMUP_ENDPOINT_LABEL,
                "success": False,
                "outcome": "skipped_unhealthy",
                "latency_ms": 0,
                "sessid_changed": False,
            })
        return

    for user_id_hash, cookies_path in users:
        if stop_event.is_set():
            return
        now = time.monotonic()
        if _should_skip_for_anti_spam(user_id_hash, now):
            _emit_event({
                "timestamp_iso": _now_iso(),
                "user_id_hash": user_id_hash,
                "trigger": "scheduler",
                "endpoint": WARMUP_ENDPOINT_LABEL,
                "success": False,
                "outcome": "skipped_recent",
                "latency_ms": 0,
                "sessid_changed": False,
            })
            continue
        try:
            _warmup_single_user(user_id_hash, cookies_path, "scheduler", stop_event)
        except Exception:  # noqa: BLE001
            logger.exception("keepalive: warmup_single_user crashed")


def _drain_nudges(stop_event: threading.Event, deadline_monotonic: float) -> None:
    """Pull from NUDGE_QUEUE until deadline or stop_event.

    Uses NUDGE_QUEUE.get(timeout=NUDGE_POLL_INTERVAL_S) so nudge-to-warmup
    dispatch stays under PERF-04's 500 ms budget (poll interval = 0.25 s).
    """
    while not stop_event.is_set():
        remaining = deadline_monotonic - time.monotonic()
        if remaining <= 0:
            return
        try:
            user_id_hash = NUDGE_QUEUE.get(timeout=min(NUDGE_POLL_INTERVAL_S, remaining))
        except queue.Empty:
            continue
        try:
            # Resolve hash back to cookies_path via full user list. For
            # family-scale (~5 users) this is cheap. If nudge hash is not
            # found (e.g. stale guest id), we silently drop it.
            now = time.monotonic()
            if _should_skip_for_anti_spam(user_id_hash, now):
                _emit_event({
                    "timestamp_iso": _now_iso(),
                    "user_id_hash": user_id_hash,
                    "trigger": "app_open",
                    "endpoint": WARMUP_ENDPOINT_LABEL,
                    "success": False,
                    "outcome": "skipped_recent",
                    "latency_ms": 0,
                    "sessid_changed": False,
                })
                continue
            if not _pool_is_healthy():
                _emit_event({
                    "timestamp_iso": _now_iso(),
                    "user_id_hash": user_id_hash,
                    "trigger": "app_open",
                    "endpoint": WARMUP_ENDPOINT_LABEL,
                    "success": False,
                    "outcome": "skipped_unhealthy",
                    "latency_ms": 0,
                    "sessid_changed": False,
                })
                continue
            # Find cookies_path for this hash
            match_path = None
            for uh, p in _collect_linked_users():
                if uh == user_id_hash:
                    match_path = p
                    break
            if not match_path:
                logger.debug("keepalive: nudge for unknown user %s", user_id_hash)
                continue
            _warmup_single_user(user_id_hash, match_path, "app_open", stop_event)
        except Exception:  # noqa: BLE001
            logger.exception("keepalive: nudge processing crashed")


def start_warmup_loop(stop_event: threading.Event) -> None:
    """Daemon entry point. Spawned by scheduler_service.main()."""
    try:
        logger.info("keepalive: started (boot grace %.0fs)", BOOT_GRACE_S)
        if stop_event.wait(BOOT_GRACE_S):
            return
        while not stop_event.is_set():
            cycle_start = time.monotonic()
            try:
                _run_cycle(stop_event)
            except Exception:  # noqa: BLE001
                logger.exception("keepalive: cycle crashed")
            deadline = cycle_start + CYCLE_INTERVAL_S
            _drain_nudges(stop_event, deadline)
    except Exception:  # noqa: BLE001 - never kill scheduler process
        logger.exception("keepalive: fatal thread exit")


def reset_state_for_tests() -> None:
    """Clear module-level state. Only for pytest fixtures."""
    with _STATE_LOCK:
        _LAST_WARMUP_AT.clear()
        CART_ADD_ACTIVE.clear()
    while not NUDGE_QUEUE.empty():
        try:
            NUDGE_QUEUE.get_nowait()
        except queue.Empty:
            break


__all__ = [
    "start_warmup_loop",
    "CART_ADD_ACTIVE",
    "NUDGE_QUEUE",
    "hash_user_id",
    "reset_state_for_tests",
    "WARMUP_JSONL_PATH",
    "CYCLE_INTERVAL_S",
    "ANTI_SPAM_WINDOW_S",
]

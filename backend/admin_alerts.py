"""Admin alert sender for operator visibility.

Phase 80 (v1.25 OBS-08/09/10). Standalone module that sends Telegram
DMs to admin chats via raw Bot API — no PTB Application dependency, so
scheduler, backend, and any other Python process can call into it
without coordinating with the running bot process.

Closes the "time-to-notice" gap from v1.24: 2026-05-13 saw a ~60-min
VLESS pool outage that the operator learned about only by opening the
MiniApp. Alerts fire on pool-dead, breaker transitions, and xray
restart failures.

Env configuration:
    TELEGRAM_TOKEN           — bot token (already used by bot/notifier.py)
    ADMIN_TELEGRAM_CHAT_IDS  — comma-separated chat IDs. Empty → no-op
                               (alerts disabled in dev / missing config).

Dedupe ledger at ``data/admin_alerts.jsonl``::

    {"ts": 1778593200.0, "kind": "pool_dead",
     "cooldown_s": 1800, "sent_to": [111, 222],
     "message": "pool_dead..."}

Per-kind cooldowns (default, overridable at call):
    pool_dead                — 30 min
    breaker_transition       — 5 min per transition type
    xray_restart_failed      — 0 s (rare; each deserves attention)
    scheduler_pool_recovered — 10 min

All I/O is best-effort. Network failure, missing token, empty chat
list → log at debug, never crash the caller. Admin alerting is
observability; it must not take the app down.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

try:
    import httpx  # scheduler/backend already depend on httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]

_logger = logging.getLogger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_LEDGER = os.path.join(_BASE_DIR, "data", "admin_alerts.jsonl")

# Overridable via env for tests / alternate deploys.
LEDGER_PATH = os.environ.get("SALEAPP_ADMIN_ALERTS_PATH") or _DEFAULT_LEDGER

# Default cooldowns (seconds). Callers can override per-alert.
DEFAULT_COOLDOWNS: dict[str, float] = {
    "pool_dead": 30 * 60,
    "scheduler_pool_recovered": 10 * 60,
    "breaker_transition": 5 * 60,
    "xray_restart_failed": 0,
    "test_alert": 0,
}

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def _get_token() -> str | None:
    """Resolve bot token from env. None → alerts disabled."""
    return os.environ.get("TELEGRAM_TOKEN") or None


def _get_admin_chat_ids() -> list[int]:
    """Parse ADMIN_TELEGRAM_CHAT_IDS env var. Empty list → alerts disabled."""
    raw = (os.environ.get("ADMIN_TELEGRAM_CHAT_IDS") or "").strip()
    if not raw:
        return []
    ids: list[int] = []
    for piece in raw.split(","):
        piece = piece.strip()
        if not piece:
            continue
        try:
            ids.append(int(piece))
        except ValueError:
            _logger.debug("Invalid admin chat id ignored: %r", piece)
    return ids


def _read_last_entry_for_kind(kind: str) -> dict | None:
    """Return the most-recent entry for ``kind`` or None. Never raises."""
    try:
        if not os.path.exists(LEDGER_PATH):
            return None
        with open(LEDGER_PATH, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
        for line in reversed(lines):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("kind") == kind:
                return entry
        return None
    except Exception:  # noqa: BLE001
        return None


def _append_entry(entry: dict) -> None:
    """Append one event line. Never raises."""
    try:
        parent = os.path.dirname(LEDGER_PATH)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(LEDGER_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, separators=(",", ":"), ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001
        _logger.debug("admin_alerts append failed", exc_info=False)


def send_admin_alert(
    kind: str,
    message: str,
    *,
    cooldown_s: float | None = None,
    force: bool = False,
    extra: dict[str, Any] | None = None,
) -> dict:
    """Send an admin DM. Dedupes via cooldown unless ``force=True``.

    Returns a status dict ``{"sent": bool, "reason": str, "sent_to": [...]}``.

    Caller contract:
        - Never raises. Any failure (missing token, HTTP error, disk
          error, missing chat list) is swallowed and recorded in the
          returned status dict.
        - ``kind`` is the dedupe key; same kind within ``cooldown_s``
          is skipped unless ``force=True``.
        - ``extra`` is persisted alongside the entry for debugging.

    Test / emergency use: pass ``force=True`` to bypass cooldown.
    """
    status: dict[str, Any] = {"sent": False, "reason": "unknown", "sent_to": []}

    token = _get_token()
    if not token:
        status["reason"] = "no_token"
        return status

    chat_ids = _get_admin_chat_ids()
    if not chat_ids:
        status["reason"] = "no_admin_chat_ids"
        return status

    if httpx is None:
        status["reason"] = "httpx_unavailable"
        _logger.debug("admin_alerts requires httpx; not installed")
        return status

    # Cooldown check.
    if not force:
        cooldown = cooldown_s if cooldown_s is not None else DEFAULT_COOLDOWNS.get(kind, 0)
        if cooldown > 0:
            last = _read_last_entry_for_kind(kind)
            if last:
                last_ts = float(last.get("ts") or 0)
                if time.time() - last_ts < cooldown:
                    status["reason"] = "cooldown_active"
                    status["cooldown_remaining_s"] = round(cooldown - (time.time() - last_ts), 1)
                    return status

    # Send. Dispatch to each chat independently so a transient 403 on one
    # doesn't block the others.
    url = _TELEGRAM_API.format(token=token)
    sent_to: list[int] = []
    errors: list[dict] = []
    for chat_id in chat_ids:
        try:
            resp = httpx.post(
                url,
                data={
                    "chat_id": chat_id,
                    "text": f"🚨 {kind.upper()}\n\n{message}",
                    "parse_mode": "HTML",
                    "disable_web_page_preview": "true",
                },
                timeout=10.0,
            )
            if resp.status_code == 200:
                sent_to.append(chat_id)
            else:
                errors.append({
                    "chat_id": chat_id,
                    "status": resp.status_code,
                    "body": resp.text[:200],
                })
        except Exception as e:  # noqa: BLE001
            errors.append({"chat_id": chat_id, "error": type(e).__name__})

    # Record the attempt regardless of outcome so cooldown applies.
    entry = {
        "ts": round(time.time(), 3),
        "kind": kind,
        "cooldown_s": cooldown_s if cooldown_s is not None else DEFAULT_COOLDOWNS.get(kind, 0),
        "sent_to": sent_to,
        "message": message[:500],  # cap message size in ledger
    }
    if errors:
        entry["errors"] = errors
    if extra:
        entry["extra"] = extra
    _append_entry(entry)

    if sent_to:
        status["sent"] = True
        status["reason"] = "ok"
        status["sent_to"] = sent_to
    else:
        status["sent"] = False
        status["reason"] = "all_recipients_failed"
        status["errors"] = errors
    return status


def read_recent(limit: int = 50) -> list[dict]:
    """Tail the last ``limit`` entries for admin inspection. [] on read error."""
    try:
        if not os.path.exists(LEDGER_PATH):
            return []
        with open(LEDGER_PATH, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
        out: list[dict] = []
        for line in lines[-limit:]:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out
    except Exception:  # noqa: BLE001
        return []

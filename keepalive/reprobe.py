"""v1.21 REL-13: Admitted-Node Self-Healing Loop.

Daemon thread spawned by :func:`scheduler_service.main`. Every
:data:`REPROBE_INTERVAL_S` (10 min by default) it iterates the admitted
VLESS host list from :meth:`vless.manager.VlessProxyManager.iter_admitted_hosts`
and re-runs ``_probe_vkusvill`` through the running bridge. Probe
failures route the host into the existing 4 h VkusVill cooldown via
``mark_vkusvill_blocked``.

Unlike admission-time probes (which spawn a fresh xray subprocess per
candidate), steady-state re-probes go through the live bridge — that's
what actual production traffic sees, so a probe failure here means
"the production path for this host is dead right now" rather than
"the admission-time handshake failed". See
``.planning/phases/67-admitted-node-self-healing-loop/67-CONTEXT.md``
§SPEC Lock for the decisions behind this behaviour.

Emits one JSONL line per cycle to ``data/proxy_events.jsonl`` so ops can
post-mortem any pool degradation. Never kills the scheduler process: all
failure paths are caught and logged.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# SPEC-locked constants from 67-CONTEXT.md §Locked Defaults.
REPROBE_INTERVAL_S = 600.0        # 10 min — re-probe cadence.
REPROBE_BOOT_GRACE_S = 120.0      # 2 min — let the scheduler settle before cycle 1.

_BASE_DIR = Path(__file__).resolve().parent.parent
PROXY_EVENTS_PATH = _BASE_DIR / "data" / "proxy_events.jsonl"


def _emit_event(event: str, payload: dict) -> None:
    """Append one JSON line to ``data/proxy_events.jsonl``. Best-effort.

    Never raises; a corrupt filesystem must not take the scheduler down.
    """
    try:
        line = json.dumps(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "event": event,
                **payload,
            },
            ensure_ascii=False,
        )
        PROXY_EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with PROXY_EVENTS_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:  # noqa: BLE001 — event emit is best-effort
        logger.debug("reprobe: event emit failed", exc_info=True)


def _run_cycle(proxy_manager, stop_event: threading.Event) -> dict:
    """Re-probe each admitted host once. Returns cycle summary dict.

    For every host returned by ``proxy_manager.iter_admitted_hosts()``:

      1. Call ``proxy_manager._probe_vkusvill(proxy=None)`` — goes through
         the running local xray bridge, same path production traffic takes.
      2. Record the outcome via ``record_outcome`` so the REL-15 sliding
         window stays up-to-date.
      3. On failure, route the host to ``mark_vkusvill_blocked`` with
         ``reason="reprobe_fail"`` — the existing 4 h cooldown machinery
         handles removal + xray config rebuild.

    Honors ``stop_event`` between hosts for a prompt shutdown. The
    returned summary is consumed by :func:`start_reprobe_loop` for the
    JSONL cycle event.
    """
    hosts = proxy_manager.iter_admitted_hosts()
    summary = {
        "admitted_count": len(hosts),
        "probed": 0,
        "passed": 0,
        "failed_hosts": [],
    }
    for host in hosts:
        if stop_event.is_set():
            break
        try:
            # proxy=None routes through the running bridge (127.0.0.1:10808).
            ok = proxy_manager._probe_vkusvill(proxy=None)  # noqa: SLF001
        except Exception:  # noqa: BLE001 — probe must never crash the cycle
            ok = False
        summary["probed"] += 1
        try:
            proxy_manager.record_outcome(host, success=ok)
        except Exception:  # noqa: BLE001 — recording is best-effort
            logger.debug("reprobe: record_outcome failed for %s", host, exc_info=True)
        if ok:
            summary["passed"] += 1
        else:
            summary["failed_hosts"].append(host)
            try:
                proxy_manager.mark_vkusvill_blocked(host, reason="reprobe_fail")
            except Exception:  # noqa: BLE001
                logger.debug(
                    "reprobe: mark_vkusvill_blocked failed for %s",
                    host,
                    exc_info=True,
                )
    return summary


def start_reprobe_loop(stop_event: threading.Event, proxy_manager) -> None:
    """Daemon entry point. Spawned by :func:`scheduler_service.main`.

    Sleeps ``REPROBE_BOOT_GRACE_S`` on first entry, then loops with
    ``REPROBE_INTERVAL_S`` between cycles. Both waits are interruptible
    via ``stop_event`` for clean shutdown. Emits a
    ``reprobe_cycle_complete`` JSONL event after each cycle (even when
    the cycle crashed, with a zeroed summary) so ops can correlate
    daemon liveness against pool drift.
    """
    try:
        logger.info("reprobe: started (boot grace %.0fs)", REPROBE_BOOT_GRACE_S)
        if stop_event.wait(REPROBE_BOOT_GRACE_S):
            return
        while not stop_event.is_set():
            cycle_start = time.monotonic()
            try:
                summary = _run_cycle(proxy_manager, stop_event)
            except Exception:  # noqa: BLE001 — cycle-level crash guard
                logger.exception("reprobe: cycle crashed")
                summary = {
                    "admitted_count": 0,
                    "probed": 0,
                    "passed": 0,
                    "failed_hosts": [],
                }
            duration_ms = int((time.monotonic() - cycle_start) * 1000)
            _emit_event(
                "reprobe_cycle_complete",
                {**summary, "duration_ms": duration_ms},
            )
            # Sleep until next cycle, interruptible by stop_event.
            if stop_event.wait(REPROBE_INTERVAL_S):
                return
    except Exception:  # noqa: BLE001 — never kill the scheduler process
        logger.exception("reprobe: fatal thread exit")


__all__ = [
    "start_reprobe_loop",
    "_run_cycle",
    "REPROBE_INTERVAL_S",
    "REPROBE_BOOT_GRACE_S",
    "PROXY_EVENTS_PATH",
]

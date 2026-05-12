# Phase 80 — Telegram Alerts + Admin Escape Hatches
**Milestone:** v1.25 Operator Visibility + Test Coverage
**Requirements:** OBS-08, OBS-09, OBS-10, OPS-24, OPS-25
**Started:** 2026-05-13

## Goal

Close the "time-to-notice" gap from v1.24. Operator must learn of VLESS pool outage via Telegram within 10 min of onset, not via user-facing MiniApp 60+ min later. Add ops escape hatches so a false-positive quarantine or UI-regression testing is one HTTP POST away.

## Design

### Admin notifier module (`backend/admin_alerts.py`)

Standalone module that sends admin DMs via raw Telegram Bot API (`https://api.telegram.org/bot<TOKEN>/sendMessage`) using `httpx`. No dependency on the PTB `Application` or the running bot process — scheduler, backend, and any other Python process can call `send_admin_alert(kind, message)` without coordination.

**Why direct API vs through PTB bot:** PTB Bot() is tied to the running bot process. Scheduler/backend are separate systemd services. Simplest path is the HTTP API call with the token.

**Env vars:**
- `TELEGRAM_TOKEN` (existing) — the bot token
- `ADMIN_TELEGRAM_CHAT_IDS` (new, comma-separated) — which chats get admin alerts. Empty → no-op (alerts disabled in dev).

**Dedupe ledger** — `data/admin_alerts.jsonl`:
```json
{"ts": 1778593200.0, "kind": "pool_dead", "cooldown_s": 1800, "sent_to": [111, 222]}
```

Before sending, check most-recent entry with same `kind`; if `now - last_ts < cooldown_s`, skip.

**Cooldowns:**
- `pool_dead`: 30 min per incident
- `breaker_transition`: 5 min per transition type (closed→open, open→half_open, half_open→closed)
- `xray_restart_failed`: 0s (rare; each deserves attention)
- `scheduler_pool_recovered`: 10 min (confirmation that recovery happened)

### Integration points

**OBS-08 — pool dead > 10 min:**
- Scheduler emits `scheduler_pool_dead` already (v1.24 REL-19)
- Add periodic check in scheduler main loop: if pool 0 for > 10 min consecutive, fire `pool_dead` alert

**OBS-09 — breaker state transitions:**
- Hook into `_persist_breaker_state` in `scheduler_service.py` (v1.19 Phase 59)
- Diff old vs new state; if changed, fire `breaker_transition` alert

**OBS-10 — xray_restart_failed:**
- Hook into `vless/manager.py::_reload_or_restart_xray` failure path
- Fire `xray_restart_failed` alert on exception or non-zero exit

### Admin escape endpoints

`backend/main.py` additions (admin-token-authed):

**OPS-24 — `POST /admin/vless/quarantine/clear`:**
```python
@app.post("/admin/vless/quarantine/clear")
def admin_clear_quarantine(token: str = Header(..., alias="X-Admin-Token")):
    _require_token(token)
    from vless import quarantine
    prev = quarantine.snapshot()
    quarantine.clear_all()
    return {"cleared_count": prev["count"], "previous_entries": prev["hosts"]}
```

**OPS-25 — `POST /admin/force-stale-all`:**
```python
@app.post("/admin/force-stale-all")
def admin_force_stale_all(token: str = Header(...), duration_s: int = 600):
    _require_token(token)
    # Set time-limited override. /api/products checks this before normal freshness logic.
    global _FORCE_STALE_UNTIL
    _FORCE_STALE_UNTIL = time.time() + max(30, min(duration_s, 3600))
    return {"force_stale_until": _FORCE_STALE_UNTIL, "duration_s": duration_s}
```

`/api/products` endpoint checks the override flag and synthesizes `staleAll` response when active.

## Non-Goals

- **No admin UI for alert config** — env var is simpler
- **No rate-limit logic beyond per-kind cooldowns** — family-scale, not enterprise
- **No PTB dependency in new module** — keeps it usable from scheduler/backend without bot-process coordination
- **No Telegram inline-keyboard actions on alerts** — alerts are read-only notifications

## Files Touched

| File | Change |
|---|---|
| `backend/admin_alerts.py` (new) | Direct Telegram API sender + dedupe ledger |
| `config.py` | Add `ADMIN_TELEGRAM_CHAT_IDS` env var loader |
| `scheduler_service.py` | Hook pool-dead timer + breaker-transition hook into admin_alerts |
| `vless/manager.py` | Hook xray-restart-failed into admin_alerts |
| `backend/main.py` | Add `/admin/vless/quarantine/clear` + `/admin/force-stale-all` endpoints |
| `backend/test_admin_alerts.py` (new) | Unit tests for send + dedupe + cooldown |
| `backend/test_admin_endpoints.py` (new) | Unit tests for the 2 new admin endpoints |
| `scripts/verify_v1.25.sh` | Phase 80 smoke checks |

## Plan Order

1. **80-01**: `backend/admin_alerts.py` module + unit tests
2. **80-02**: Hook into scheduler (pool-dead + breaker) + vless manager (xray-restart) + config changes
3. **80-03**: `/admin/vless/quarantine/clear` + `/admin/force-stale-all` + unit tests + live EC2 verification

## Success Criteria

1. [ ] `send_admin_alert(kind, message, cooldown_s)` sends Telegram DM to every chat in `ADMIN_TELEGRAM_CHAT_IDS`
2. [ ] Dedupe via `data/admin_alerts.jsonl` — same kind within cooldown = skip
3. [ ] Pool-dead > 10 min triggers alert (OBS-08)
4. [ ] Breaker state transition triggers alert (OBS-09)
5. [ ] `xray_restart_failed` event triggers alert (OBS-10)
6. [ ] `POST /admin/vless/quarantine/clear` clears `pool_quarantine.json` + returns diff (OPS-24)
7. [ ] `POST /admin/force-stale-all` sets time-limited override forcing staleAll response (OPS-25)
8. [ ] Unit tests green
9. [ ] Live EC2: fire test alert, verify admin receives DM within seconds
10. [ ] v1.24 + earlier regression green

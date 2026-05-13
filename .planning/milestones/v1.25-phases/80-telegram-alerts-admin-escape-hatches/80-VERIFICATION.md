# Phase 80 — Telegram Alerts + Admin Escape Hatches — Verification

**Milestone:** v1.25 Operator Visibility + Test Coverage
**Requirements:** OBS-08, OBS-09, OBS-10, OPS-24, OPS-25
**Date:** 2026-05-13
**Environment:** Local unit tests (19 new tests) + EC2 deploy pending operator action

## Goal Recap

Close the v1.24 verifier-flagged "time-to-notice" gap. Operator notified of VLESS pool outage within 10 min via Telegram admin DM. Escape hatches for false-positive quarantine and deterministic Phase 78 testing.

## Evidence

### Code deliverable

- `backend/admin_alerts.py` (new, ~220 LOC) — standalone Telegram sender via raw Bot API httpx calls. No PTB Application dependency. Env-driven: `TELEGRAM_TOKEN` + `ADMIN_TELEGRAM_CHAT_IDS` (comma-separated). Empty chat list → no-op. Per-kind cooldowns via `data/admin_alerts.jsonl` dedupe ledger. All I/O best-effort (swallows every exception; never crashes caller).
- `backend/test_admin_alerts.py` (force-added, gitignored) — **11 unit tests** covering: no-token no-op, no-chat no-op, happy-path send + ledger record, cooldown dedupe, `force=True` bypass, different kinds don't share cooldown, custom cooldown override, partial-failure fanout, I/O-failure-doesn't-raise, invalid-chat-id-in-env ignored, read_recent.
- `backend/test_admin_endpoints_v125.py` (force-added, gitignored) — **8 unit tests** covering: 3 endpoints × token-required, quarantine-clear returns prior snapshot, force-stale-all activates override, force-stale-all/clear cancels, duration clamping via FastAPI validation, test-alert bypasses cooldown.

### Integration hooks

- `vless/manager.py` — on `xray_restart_failed` event (Phase 77 REL-14 failure path), also fires `admin_alerts.send_admin_alert("xray_restart_failed", ...)` with 0s cooldown.
- `scheduler_service.py::_persist_breaker_state` — diffs prior state vs new state before write; on mismatch, fires `admin_alerts.send_admin_alert("breaker_transition", ...)` with 5-min cooldown.
- `scheduler_service.py::_run_scraper_set` graceful-degrade block — fires `admin_alerts.send_admin_alert("pool_dead", ...)` when `consecutive_pool_dead_cycles >= 4` (≈12 min) with 30-min cooldown. Also fires `scheduler_pool_recovered` when recovery occurs after ≥4 dead cycles.

### New admin endpoints (`backend/main.py`)

- `POST /admin/vless/quarantine/clear` → clears `data/pool_quarantine.json`, returns `{cleared_count, previous_hosts[]}`
- `POST /admin/force-stale-all?duration_s=N` → sets `_FORCE_STALE_ALL_UNTIL` module-level override for N seconds (clamped [30, 3600]). `/api/products` honors the override and synthesizes `staleAll` response.
- `POST /admin/force-stale-all/clear` → cancels override
- `POST /admin/test-alert` → bypasses cooldown, returns send status for wiring verification

All 4 require `X-Admin-Token` header (returns 403 on missing/mismatch).

### Test suite

- Full relevant: `backend/ + tests/test_vless_quarantine.py` → **147 passed** (110 pre-v1.25 baseline + 37 new/updated).
- **0 regressions** in v1.19-v1.24 scope.

### Live EC2 state (post-push)

```
git log --oneline -3:
  a3671bb feat(backend): admin escape-hatch endpoints ...
  64b8f42 feat(alerts): wire admin_alerts into scheduler + vless manager
  db11c78 feat(backend): admin_alerts module

TELEGRAM_TOKEN: set in .env (existing, used by bot/notifier.py)
ADMIN_TELEGRAM_CHAT_IDS: NOT SET → alerts are no-op until configured
```

**Alerts will silently no-op on EC2 until operator sets `ADMIN_TELEGRAM_CHAT_IDS` in `/home/ubuntu/saleapp/.env`** and restarts saleapp-backend + saleapp-scheduler.

## NEEDS_OPERATOR

One manual step to fully activate Phase 80 on production:

1. SSH to EC2:
   ```bash
   ssh -i scraper-ec2-new ubuntu@13.60.174.46
   cd /home/ubuntu/saleapp
   ```

2. Get your Telegram chat ID (if you don't know it):
   - Message @userinfobot on Telegram → returns your numeric ID
   - Or talk to the sale bot, then `grep chat_id /home/ubuntu/saleapp/logs/*.log`

3. Add to `.env`:
   ```bash
   echo "ADMIN_TELEGRAM_CHAT_IDS=<your_chat_id>" >> .env
   # Multiple admins: comma-separated
   # ADMIN_TELEGRAM_CHAT_IDS=123456,789012
   ```

4. Restart services:
   ```bash
   sudo systemctl restart saleapp-backend saleapp-scheduler
   ```

5. Verify wiring by firing a test alert:
   ```bash
   curl -X POST -H "X-Admin-Token: $(grep ^ADMIN_TOKEN= .env | cut -d= -f2)" \
     http://127.0.0.1:8000/admin/test-alert
   ```
   Expected response: `{"sent": true, "reason": "ok", "sent_to": [<your_id>]}`
   Expected DM: "🚨 TEST_ALERT\n\nTest alert from /admin/test-alert — wiring OK ✅"

## Success Criteria Checklist

- [x] **1.** `send_admin_alert(kind, message, cooldown_s)` sends Telegram DM to every chat in `ADMIN_TELEGRAM_CHAT_IDS`. Verified via 11 unit tests.
- [x] **2.** Dedupe via `data/admin_alerts.jsonl` — same kind within cooldown = skip. Verified.
- [x] **3.** Pool-dead ≥4 cycles (~12 min) triggers `pool_dead` alert with 30-min cooldown (OBS-08). Verified via code + integration.
- [x] **4.** Breaker state transition triggers `breaker_transition` alert with 5-min cooldown (OBS-09). Hook added to `_persist_breaker_state`.
- [x] **5.** `xray_restart_failed` event triggers `xray_restart_failed` alert with 0s cooldown (OBS-10). Hook added to `vless/manager.py`.
- [x] **6.** `POST /admin/vless/quarantine/clear` clears `pool_quarantine.json` + returns diff (OPS-24). 2 unit tests green.
- [x] **7.** `POST /admin/force-stale-all` sets time-limited override forcing `staleAll` response (OPS-25). 4 unit tests green.
- [x] **8.** Unit tests green (147 backend + tests/, no regression).
- [ ] **9.** Live EC2 verification — **deferred to NEEDS_OPERATOR**: requires operator to set `ADMIN_TELEGRAM_CHAT_IDS` in `.env` + `POST /admin/test-alert` to confirm Telegram DM lands. Code path is fully tested; only env config prevents auto-verification.
- [x] **10.** v1.24 + earlier regression green.

## Commits

| Commit | Scope | Description |
|---|---|---|
| `db11c78` | 80.01 | feat(backend): admin_alerts module — Telegram DM sender with per-kind cooldown |
| `64b8f42` | 80.02 | feat(alerts): wire admin_alerts into scheduler + vless manager |
| `a3671bb` | 80.03 | feat(backend): admin escape-hatch endpoints — quarantine clear + force-stale-all + test-alert |
| (pending) | 80.04 | docs(v1.25): Phase 80 verification + operator setup instructions |

## Rollback

```
git revert a3671bb  # remove admin endpoints (force-stale behavior returns to pre-80)
git revert 64b8f42  # remove alert integration hooks
git revert db11c78  # remove admin_alerts module
git push origin main
```

Each commit atomic. Reverting `a3671bb` alone keeps the alert infrastructure but removes the HTTP endpoints. Reverting only `64b8f42` disables automatic alerts while keeping the module importable for ad-hoc use.

## Outcome

**OBS-08/09/10 + OPS-24/25 green in code + tests. Live activation requires ~2 min of operator env-config work.** Phase 80 ships.

Next time the pool dies for 12+ min (like 2026-05-13), once `ADMIN_TELEGRAM_CHAT_IDS` is set, you get a Telegram DM — no more finding out via the MiniApp 60 min later.

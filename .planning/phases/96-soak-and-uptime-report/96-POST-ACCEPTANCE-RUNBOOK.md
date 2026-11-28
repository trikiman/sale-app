# Phase 96 — Runbook After Acceptance (28.11 07:10 MSK Onward)

Verified facts as of 2026-11-27 21:14 MSK (live endpoint + `ssh vless` read-only):

- Last gap (#11, 97.7 min) has `from_ts` = `2026-11-21 07:10 MSK` and leaves the 168 h window at **2026-11-28 07:10 MSK** (gaps exit at `from_ts + 168 h`, not `to_ts + 168 h`, per `backend/green_uptime.py:147`).
- Earlier gap (45.3 min, `from_ts` `2026-11-20 22:50 MSK`) leaves at **2026-11-27 22:50 MSK**.
- Acceptance criteria (`scripts/phase96_acceptance.py`): `false_zero_cycles == 0`, `gap_incident_count == 0`, `hours_recorded >= 167.25` (168 h minus 45-min gap threshold tolerance), and no gap after `ACCEPTANCE_EPOCH`.
- One-shot cron `08440c65ff15` is scheduled for `2026-11-28 09:05+03:00` with `catch_up = true` and `no_agent = true` (`saleapp_acceptance_check.sh`).
- Production (`vless`, `152.70.58.201`) is on commit `3485e0c`; the only functional green commit not yet on prod is `66c124e` (`scrape_green.py`: short-but-real scrape of a fresh snapshot is a degraded success, not `exit 1`). `scrape_green.py` runs as a child process per cycle (`scheduler_service.py`), so deploying it alone does not require a service restart.
- `ADMIN_TOKEN` was exposed in earlier `curl -v` output on 2026-11-27 and needs rotation on the server (which requires updating `.env` and restarting the backend).

## Rule 0: Hold Everything Until 2026-11-28 07:10 MSK

Do not restart the backend, do not touch the green scraper path, and do not run acceptance early. Restarts and mid-window changes caused prior resets of the 168 h window.

## Step 1: Verify Acceptance (at or after 2026-11-28 07:10 MSK; cron runs 09:05 MSK)

Run from `E:/Projects/saleapp`:

```bash
python scripts/phase96_acceptance.py
bash ~/.hermes/scripts/saleapp_acceptance_check.sh
```

- Exit `0`: all four checks pass (`false_zero_cycles == 0`, `gap_incident_count == 0`, `hours_recorded >= 167.25`, `0 post-epoch gap(s)`).
- Exit `2`: acceptance not met — do not close Phase 96; inspect `gap_incidents` and `false_zero_cycles` before taking action.
- Exit `3`: endpoint unreachable — check network/proxy/service health without guessing.

## Step 2: Human Actions Only After Exit 0

1. Close Phase 96 via GSD (`gsd-tools state complete-phase --phase 96`), then audit/complete milestone `v1.30` per GSD workflow.
2. Deploy `66c124e` (`scrape_green.py` short-scrape handling) to `/home/ubuntu/saleapp` on `vless` if desired (improves `uptime_pct` accuracy; does not require a backend restart).
3. Rotate `ADMIN_TOKEN` in `/home/ubuntu/saleapp/.env` and local `.env` (keep secret values out of chat/commits/memory), then restart the backend service once and verify `/api/admin/green-uptime` with the new token.

## Step 3: Deferred Accounting Defect

Several runs that found products (`live_count > 0`) exited with status `1` and incremented `cycles_failed`, lowering `uptime_pct` while leaving `gap_incident_count` and `false_zero_cycles` unaffected. Address in `scrape_green.py` / `scheduler_service.py` after Phase 96 closure.

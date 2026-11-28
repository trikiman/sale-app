# Phase 96 — runbook after acceptance (28.11 07:10 MSK onward)

Facts this is built on (verified 27.11, live + `ssh vless` read-only):

- The last gap (`from_ts` 21.11 07:10 MSK) leaves the 168 h window at **28.11 07:10 MSK**.
  Gaps exit on `from_ts + 168 h`, not `to_ts + 168 h` (`backend/green_uptime.py:147`).
- Gate = `false_zero_cycles == 0` AND `gap_incident_count == 0`; `hours_recorded >= 167.25`
  is the span criterion (`MIN_HOURS`, tolerance = the 45-min gap threshold).
- Prod is on `3485e0c`; the only functional commit it lacks is `66c124e`
  (`scrape_green.py`: short-but-real scrape = degraded success, not exit 1).
  `scrape_green.py` is spawned per cycle by `scheduler_service.py` -> **no restart needed**.
- The one-shot acceptance cron `08440c65ff15` runs 28.11 09:05 MSK with `catch_up: true`.
- `ADMIN_TOKEN` was exposed in a `curl -v` at 08:1x on 27.11.

## 0. Do not do any of this before 07:10 MSK

A backend restart, a deploy that touches the green path, or a scraper experiment inside the
window is how this phase lost four attempts already. Wait for the window.

## 1. Read the verdict (either the 09:05 cron, or by hand)

```bash
cd E:/Projects/saleapp
python scripts/phase96_acceptance.py        # exit 0 = acceptance met, 2 = not met, 3 = unreachable
bash ~/.hermes/scripts/saleapp_acceptance_check.sh
```

Expected: `[PASS] false_zero_cycles == 0`, `[PASS] gap_incident_count == 0`,
`[PASS] hours_recorded >= 167.25 ...`, `[PASS] no gap after acceptance epoch`.
If `gap_incident_count != 0`, stop: read `hermes cron runs 894c7424bbbe` and `/admin/logs` before closing anything.

## 2. Close Phase 96 and milestone v1.30 (human-owned GSD step)

Only after step 1 exits `0`:

```bash
cd E:/Projects/saleapp
gsd-tools state complete-phase --phase 96
# then audit / complete v1.30 per gsd-audit-milestone / gsd-complete-milestone
```

## 3. Deploy the parked short-scrape fix (`66c124e`)

`scrape_green.py` runs as a child process per cycle (`scheduler_service.py:410`), so updating
the file does not require restarting the backend process. Copy `scrape_green.py` to `vless:/home/ubuntu/saleapp/scrape_green.py`,
verify syntax/git status on `vless`, and watch the next green cycle.

## 4. Rotate `ADMIN_TOKEN` (last, because it restarts the backend)

`ADMIN_TOKEN` appeared in `curl -v` output on 27.11 at ~08:1x and should be treated as
compromised. Update `ADMIN_TOKEN` in `/home/ubuntu/saleapp/.env` on `vless` and in local
`E:/Projects/saleapp/.env` (keep secret values out of chat, commits, and memory), then
restart the backend service on `vless` (not `xray.service`, not gateway/Hermes.exe) and
re-verify `/api/admin/green-uptime`.

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
If `gap_incident_count != 0`, stop: read `hermes cron runs 894c7424bbbe` and
`data/green_last_failure.json` on `ssh vless` before closing anything.

## 2. Close phase 96 (human / GSD step, only after exit 0)

- Complete phase 96 in `.planning` (`gsd-tools state complete-phase --phase 96` / `ROADMAP.md`
  and `STATE.md`), then run milestone audit/completion for `v1.30` if desired.
- Pause or retire the soak/acceptance crons once closed (`894c7424bbbe`, `08440c65ff15`,
  `849ba2418e5a`, `9bedad3da8b0` as appropriate).

## 3. Deploy parked `scrape_green.py` fix (`66c124e`)

Once acceptance passes, `66c124e` is safe to ship on `ssh vless` (`git pull` / deploy
`scrape_green.py`). It does not require restarting the API/scheduler process because
`scrape_green.py` is invoked per cycle as a child process (`scheduler_service.py:410`),
and it turns short-but-real scrapes with a fresh snapshot into `ok` instead of `exit 1`.

## 4. Rotate exposed `ADMIN_TOKEN` (human action on prod)

Because `ADMIN_TOKEN` appeared in a `curl -v` output on 27.11:
1. Generate a new token and update `ADMIN_TOKEN` on `ssh vless` (server `.env`) and in
   local `E:/Projects/saleapp/.env` (without printing secret values to logs/chat).
2. Restart the backend service on `ssh vless` so the new `ADMIN_TOKEN` takes effect, then
   verify `/api/admin/green-uptime` returns HTTP 200 with the new header and 401/403 with
   the old one.

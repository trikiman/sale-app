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
cd E:/Projects/saleapp && python scripts/phase96_acceptance.py
```

Expect `exit 0` and all four checks `[PASS]`. If `gap_incident_count > 0` or
`false_zero_cycles > 0`, stop — the window was not clean; do not close the phase.

## 2. Close phase 96 and milestone v1.30 (human step)

- Close phase 96 via GSD (`gsd-tools state complete-phase --phase 96`), then run
  `gsd-audit-milestone` / `gsd-complete-milestone` for `v1.30` and check off the
  completed boxes in `.planning/ROADMAP.md` (phases 96 and 97).

## 3. Deploy `66c124e` (no restart needed)

`scrape_green.py` is invoked as a subprocess per cycle (`scheduler_service.py`), so
copying `scrape_green.py` to `/home/ubuntu/saleapp/scrape_green.py` takes effect on
the next cycle without restarting the backend service.

## 4. Rotate `ADMIN_TOKEN` (requires restart)

1. Generate a fresh token and update `ADMIN_TOKEN=` in `/home/ubuntu/saleapp/.env`
   (and local `E:/Projects/saleapp/.env` if shared — never print or commit its value).
2. Restart the backend service so the new token is loaded, then verify
   `/api/admin/green-uptime` returns HTTP 200 with the new header and HTTP 401/403
   with the old one.

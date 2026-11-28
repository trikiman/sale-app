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

Exit `0` = all mechanical checks pass. Exit `2` = a check failed — do **not** close the phase;
inspect `gap_incidents` / `false_zero_cycles` / `hours_recorded` first.

## 2. Deploy the one pending green fix (`66c124e`), no restart required

`scrape_green.py` runs as a child process each cycle (`scheduler_service.py:410`), so
updating the file on `vless` takes effect on the next cycle without restarting the service:

```bash
scp E:/Projects/saleapp/scrape_green.py vless:/home/ubuntu/saleapp/scrape_green.py
```

Check the next cycle's `green-uptime` entry (`ok: true`, `live_count > 0`) rather than trusting
the copy alone.

## 3. Rotate `ADMIN_TOKEN` (human-owned prod change + restart)

`ADMIN_TOKEN` appeared in tool output during `curl -v` on 27.11 and must be rotated.
Changing it requires updating `.env` on `vless` and restarting the backend service — which
is why it waits until step 3, after the soak window has already closed.

## 4. Close Phase 96 and milestone v1.30 (human-owned GSD transition)

Only after step 1 exits `0`:

```bash
gsd-tools state complete-phase --phase 96
```

Then run the milestone audit / completion flow for `v1.30` and check whether `ROADMAP.md`
checkboxes for completed phases (`97` and `96`) should be updated.

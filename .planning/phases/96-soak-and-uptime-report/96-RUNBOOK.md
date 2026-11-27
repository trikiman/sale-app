# Phase 96 — runbook after acceptance (28.11 07:10 MSK onward)

Facts this is built on (verified 27.11, live + `ssh vless` read-only):

- The last gap (`from_ts` 21.11 07:10 MSK) leaves the 168 h window at **28.11 07:10 MSK**.
  Gaps exit on `from_ts + 168 h`, not `to_ts + 168 h` (`backend/green_uptime.py:147`).
- Gate = `false_zero_cycles == 0` AND `gap_incident_count == 0`; `hours_recorded >= 167.25`
  is the span criterion (`MIN_HOURS`, tolerance = the 45-min gap threshold).
- Prod is on `3485e0c`; the only functional commit it lacks is `66c124e`
  (`scrape_green.py`: short-but-real scrape = degraded success, not exit 1).
  `scrape_green.py` is spawned per cycle by `scheduler_service.py` → **no restart needed**.
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
`[PASS] hours_recorded >= 167.25 …`, `[PASS] no gap after acceptance epoch`.
If `gap_incident_count != 0`, stop: read `hermes cron runs 894c7424bbbe` and do not close.

## 2. Deploy the one parked commit (only after the verdict is in)

```bash
ssh vless 'cd /home/ubuntu/saleapp && git pull --ff-only && git log --oneline -1'
```

Expect `66c124e` or later. Nothing to restart: the next green cycle picks up the new
`scrape_green.py`. Verify on the *next* cycle, not immediately:

```bash
ssh vless 'cd /home/ubuntu/saleapp && tail -1 data/green_uptime.jsonl'
```

A `preserve_ok` cycle must show `"ok": true` with `live_count >= 11` — if it ever shows
`ok: true, live_count: 0`, that is a false zero and the commit must be reverted.

## 3. Close phase 96 (human-owned)

```bash
gsd-tools state complete-phase --phase 96
```

Then `gsd-audit-milestone` / `gsd-complete-milestone` for v1.30.

## 4. Rotate `ADMIN_TOKEN` (after step 3 only)

Prod `.env` + local `.env` + every script that reads it. This one *does* restart the
backend, which is why it is last: it creates a hole in the soak record, and by then the
record is already accepted. Order matters — rotating before acceptance throws the week away.
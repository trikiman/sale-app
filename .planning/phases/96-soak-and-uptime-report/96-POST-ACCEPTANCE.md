
## 2. Close phase 96 & v1.30 (after exit 0)

- Phase close (operator/GSD): `gsd-tools state complete-phase --phase 96` (and check
  `ROADMAP.md` checkboxes for phases 96 and 97 — `97` already has summary +
  verification artifacts).
- Milestone audit / close: `gsd-audit-milestone` / `gsd-complete-milestone` for
  `v1.30` if all phases are closed.

## 3. Deploy the parked short-scrape fix (`66c124e`) + rotate `ADMIN_TOKEN`

- `66c124e` is in `scrape_green.py` (spawned per cycle by `scheduler_service.py`),
  so updating `scrape_green.py` does not require a service restart; if `backend/*.py`
  or `.env` (`ADMIN_TOKEN` rotation) is touched, restart only the saleapp service
  (never `xray.service`, nginx, gateway, or `Hermes.exe`).
- Verify after deploy: `curl -sS -x socks5h://127.0.0.1:10870 -H "X-Admin-Token: <new_token>" [http://152.70.58.201/api/admin/green-uptime?hours=24&tail=10](http://152.70.58.201/api/admin/green-uptime?hours=24&tail=10)`.

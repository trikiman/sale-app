---
gsd_state_version: 1.0
milestone: v1.30
milestone_name: Green Tag Uptime
status: Phase 97 complete
stopped_at: milestone planned; next step is `/gsd-plan-phase 94`
last_updated: "2026-11-16T10:58:02.957Z"
progress:
  total_phases: 4
  completed_phases: 3
  total_plans: 6
  completed_plans: 6
  percent: 78
---

*Session checkpoint 2026-10-19 (ops review). Milestone v1.26 remains shipped/archived. Operator milestone "Telegram Favorites Notifications" verified end-to-end on prod and closed as working. Green-уценка confirmed morning-only (VkusVill stock reality, not a bug). RU VLESS pool degraded to 1/5 — scraping survives on the manual trojan seed floor; pool replenishment is the top candidate for the next milestone.*

## Blockers

- ~~Deploy pipeline broken~~ **FIXED 2026-11-17 02:20.** Root cause: the server
  working tree had uncommitted edits (`database/sale_history.py`, `vless/sources.py`),
  so `git pull` aborted with "Your local changes would be overwritten by merge" —
  and the webhook only ever returned stdout, hiding stderr, so it looked like a
  successful update while HEAD stayed at `a923aed`. Fixed by saving the diff
  (`/home/ubuntu/server-local-changes-20261117.patch`), `git stash`, `git pull`,
  restoring the `sale_history.py` hotfix (now committed as `2819e04`), and
  restarting both services. **SSH works through the server's own SOCKS**
  (`connect -S 127.0.0.1:10870`) — port 22 is DPI-blocked directly, but reachable
  via the tunnel; that is now the supported path for server ops.
  Verified live: `[pool-watchdog] checkout=/home/ubuntu/saleapp head=043b282`,
  `Backoff state: streak=0`, `data/vless_backoff.json` written.

- **Deploy pipeline (historical note)**: every
  webhook says `pull_output: "Updating a923aed..25ec816\n"` — the same base
  every time, one line only — while repo history shows several successful
  deploys past that point. The server checkout is stuck at `a923aed` and both
  restarts (`saleapp-backend`, `saleapp-scheduler`) keep bringing up the old
  code: the backoff commit never executed (no `Backoff state:` log line, no
  `[pool-watchdog] checkout=` diagnostics line, `pull_output` still truncated at
  200 chars after the commit that raises it to 1500). The merge presumably fails
  (dirty tree / local commits — an earlier webhook showed base `d51c257`, a hash
  that does not exist in our history) and the error is swallowed. **Fixing
  requires SSH** (`git -C /home/ubuntu/saleapp status; git pull; systemctl
  restart saleapp-backend saleapp-scheduler`) — port 22 is DPI-blocked.
  Until then: commits after `a923aed` are NOT live on the server.

- **VLESS pool 0/5 healthy** (diagnosed 2026-11-17 00:15, card `t_742784ed`).
  Fetch is healthy: `parsed=1587, geo ru=422, uniq host:port=231`; TCP pre-filter
  `102/152 reachable`. Then **xray probe fails on all 152** (`probe_error=102,
  tcp_unreachable=50`) → pool 0. So the bottleneck is the **tunnel**, not the
  sources: TCP opens but no node proxies. Probe target is already correct
  (`https://vkusvill.ru/favicon.ico`). Next hypotheses: probe timeout too tight
  for reality nodes from Amsterdam; flow/SNI/fingerprint not passed verbatim;
  nodes demand RU egress.

  **After raising the probe budget to 20 s (commit `5314f21`) the rejection
  buckets changed shape** — 231 candidates turned into
  `probe_error=104, vpn_detected=66, tcp_unreachable=50, egress_country_non_ru=11`,
  still 0 admitted. The `vpn_detected=66` bucket is the finding: those nodes DO
  tunnel traffic, and VkusVill answers them with the VPN-flagged page. Public
  free VLESS lists are datacenter IPs, and VkusVill blocks datacenter egress by
  design — that is why the residential URnetwork route works (`urnetwork ok`,
  `basket_recalc: success=Y`) while 231 free nodes yield nothing.

  **Conclusion:** the pool cannot be fixed by collecting more free lists. Either
  the pool moves to residential RU egress, or it is retired as a green-egress
  path and URnetwork becomes primary with the pool as a best-effort extra.
  Do not spend more cycles hunting free nodes for VkusVill.

  Green cycles survive on URnetwork (`urnetwork ok`).
- **Telegram notifications dead**: bot not polled server-side, `/admin/test-alert`
  → `no_admin_chat_ids`; needs SSH (port 22 blocked by DPI).

## Session

**Last session:** 2026-11-16 (v1.30: phases 94, 95, 97 closed; Phase 96 soak running)
**Stopped at:** soak in progress (168 h, verdict 2026-11-23); instrumentation + daily cron live
**Resume file:** None

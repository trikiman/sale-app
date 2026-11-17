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

## Ops done 2026-11-17 (v1.30 hardening)

- **Log rotation installed** (was missing entirely): `logs/scheduler.log` had grown
  to **326 MB**, which is why `/admin/logs` needed >90 s and kept timing out.
  `/etc/logrotate.d/saleapp`: `su ubuntu ubuntu`, daily, `size 50M`, rotate 5,
  compress, delaycompress, copytruncate. Applied immediately: history trimmed to
  a 2.3 MB `.gz`, live file restarted at 0. Verified: `/admin/logs` answers in
  **0.87 s** (was >90 s timeout).
- **SSH via the server's own SOCKS** is the supported ops path
  (`connect -S 127.0.0.1:10870`) — see the deploy note below.
- **Pool probe budget** raised to 20 s (commit `5314f21`) — pool admitted a node
  (`Pool now has 1 nodes`, `active_outbounds: 1`), then lost it; free lists are
  still ~98% dead, URnetwork carries the traffic.
- **Empty-refresh backoff verified live**: intervals went from 60 s to 26 min
  (`data/vless_backoff.json` → `{"empty_streak": 1}`, 30 min after streak ≥ 2).

## Found 2026-11-17 03:27 — why green cycles are sparse (new, not yet fixed)

`green_uptime.jsonl` had no new record between 03:10 and 03:28 while the scheduler
was busy the whole time. The cycle is **sequential** (RED → YELLOW → GREEN), and
`scrape_yellow.py` hangs: the log shows `TIMEOUT scrape_yellow.py killed after 420s`
twice in a row (02:07, 02:29) and a `YELLOW-RETRY` in progress at 03:26. With the
420 s watchdog plus the retry pass, one stuck yellow run can occupy ~14 minutes
and the green pass simply never gets its turn — so the soak under-counts green
cycles for a reason that has nothing to do with green.

Also fixed on this pass: the soak recorder was gated on a strict `tag == "GREEN"`,
so every retried cycle (`GREEN-RETRY`) was dropped — `eee19ba`, 3 tests.

**Fixed on this pass** (commit `fc67414`): a TIMEOUT no longer triggers an
immediate retry — the turn is dropped and the next cycle starts with a fresh
Chrome. A real failure (exit 1, proxy at fault) still retries. Live proof:
`03:40:49 GREEN: OK (data updated)` and a new soak record
(`ts 1794886849, ok=true, dur=238.6`) — the first green record after 03:10.

**Fixed** (commit `dde9ad4`): GREEN moved to the front of the full cycle
(`green, red, yellow`), so a hung yellow can no longer push it out. Verified live:
`04:15:48 Starting scrape_green.py` → `04:19:38 scrape_red.py`, and records now
arrive every ~10 min with real data — `07:19 ok live=47`, `/api/products` green 10
and climbing (morning markdown). Soak is honest again, and the hang class is closed: records now show
`live=10 → 47 → 71` (morning markdown), and the 446–470 s kills are gone —
`page.get()` had no deadline and sat on a dead tunnel for 7 minutes after
`Loaded 48/48 cookies via CDP`. All three navigation sites now go through
`_page_get()` with a 90 s `asyncio.wait_for` (`2c7dd91`, 4 tests), so a stalled
tunnel costs 90 s instead of a lost cycle. Observed after deploy: three
consecutive `GREEN: OK` (04:23, 04:34, 04:40), one run taking 646 s but
completing, and a pre-existing `Page reload timed out after 45s — skipping
basket_recalc` guard doing its job.

## Session

**Last session:** 2026-11-16 (v1.30: phases 94, 95, 97 closed; Phase 96 soak running)
**Stopped at:** soak in progress (168 h, verdict 2026-11-23); instrumentation + daily cron live
**Resume file:** None

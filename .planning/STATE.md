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

## Audit 2026-11-18 00:02 MSK — history, prices, front-end all live

- `/api/history/products` and `/api/history/product/{id}` serve real data: `Морковь`
  (id 606) has `last_known_price 32.0`, `total_sale_count 30`, `last_sale_at 20:54:53Z`
  (8 min old) and a price-time prediction. **Correcting my own earlier reading:** I
  compared that timestamp to a "now" sampled hours before and briefly called it
  "future time" — it was not; the real clock was 21:02 UTC.
- `/api/products`: 161 products, `greenLiveCount 3` (night lull, same as 17:07), a
  green entry reads `Морковь 32 / 53`, prices present, `updated 2026-11-18 00:00:14`.
- `https://vkusvillsale.vercel.app/` → HTTP 200.
- SSH via the local SOCKS is currently **unavailable** (`connect` SOCKS 0x00 then an
  empty banner → `Connection closed by UNKNOWN port 65535`): the balancer picked a
  node that drops :22. Not touching the proxy; ops work goes through the API and
  the git webhook until it recovers. `VACUUM` on the 575 MB `salebot.db` waits for
  SSH.

## Endpoint audit 2026-11-18 01:55 MSK (all public routes)

Called through the live front `https://vkusvillsale.vercel.app`:

| endpoint | result |
|---|---|
| `/api/products` | 200, 186 products, 13 fields each |
| `/api/new-products` | 200, `{new_products, count}` → count 0 (nothing new at night) |
| `/api/groups` | 200, 71 groups |
| `/api/history/products` | 200, `{products, total, page, pages, per_page}`, per_page 50 |
| `/api/history/product/{id}` | 200, price + sale count + prediction |
| `/api/health/deep` | 503 `degraded` — only `pool_below_min_healthy:0_lt_5` |
| `/admin/green-uptime` | 200, 172 cycles / 89.53% |
| `/admin/test-alert` | 200 `{"sent": true}` |
| `/admin/egress-probe` | ok (earlier check) |

**SSH is still down:** the SOCKS CONNECT on `:22` succeeds (reply code `0x00`) but no
banner ever arrives — `empty-banner` on every attempt, 40+ min. That is a different
failure from the earlier `Connection closed`: the tunnel reaches the host and the
TCP handshake completes, but sshd does not speak. Not touching the proxy or the
server's unit files; everything in the audit above was done over HTTP. `VACUUM`
of the 575 MB `salebot.db` stays pending until SSH returns.

## Data quality spot-check 2026-11-18 01:40 MSK (186 products)

Checked through the public front (`https://vkusvillsale.vercel.app/api/products`):

- **0** products without `currentPrice`, **0** without `oldPrice`;
- **0** products where `oldPrice <= currentPrice` (that would render a fake "−0%" badge);
- **0** products with `stock = 0`;
- distribution `green 1 / red 43 / yellow 142` — night lull, matches the soak record `live=1`.

`discount` is **not** an API field (13 fields per product) and the front never reads it:
the bundle computes `Math.round((1 - currentPrice/oldPrice) * 100)` only when
`oldPrice > currentPrice` (verified in `assets/index-CcGxQfVB.js`). So `Monini 685/1268`
renders as **−46%**, correctly derived — no missing-field bug here. My earlier note that
`discount` came back `None` was reading a field the API simply does not expose.

## End-to-end verified 2026-11-18 01:25 MSK (front-end → API → server)

`https://vkusvillsale.vercel.app/api/products` → **200, 183 products, greenLiveCount 1**
(`Monini 685 / 1268`) — identical to what the server API returns at the same moment
(`live=1` in the newest soak record). So the Vercel front-end proxies `/api/*` to this
server and the data is not stale. The deployed bundle hash `assets/index-CcGxQfVB.js`
is the same artefact the local build now produces, so Vercel and the server share
the current source.

Practical note: the browser tool refuses this host ("private or internal address" —
the proxy resolves it internally), so end-to-end checks go through `curl` against
the public host; that path works and is what produced the numbers above.

## Soak trending healthy after the navigation deadline (2026-11-17 09:05 UTC)

Nine consecutive successful cycles since `2c7dd91` (06:40 → 09:05 UTC), **zero**
`exit=-9` kills in that window: `62 ok / 17 failed` overall, but every failure is
older than the fix. `false_zero_count: 0`, uptime 78.48% (the 17 historical
failures stay in the 168 h window by design).

Cost side, stated plainly: removing the hangs made cycles longer where the tunnel
was slow — one run took **821 s** (26 products) and completed, another 646 s. The
watchdog only fires on silence, so these now finish instead of dying. Remaining
inefficiency is card-by-card basket enrichment, not the network.

One load-related event at 06:04 UTC: `Page reload timed out after 45s — skipping
basket_recalc (using modal data + data-max)` — the existing guard degraded
gracefully instead of hanging.

## Telegram + miniapp audited 2026-11-17 08:55 MSK

**Telegram works — the earlier "bot is not polled" note was wrong.**
- `saleapp-bot` (main.py, python-telegram-bot) polls `getUpdates` every 10 s, HTTP 200.
- `scheduler_service._run_merge_and_notifier()` runs `backend/notifier.py` each cycle
  (`NOTIF: OK (notifications run)`), which calls `run_notification_cycle`.
- Delivery proof: `notification_history` rows are written **only after** a successful
  `send_message` (bot/notifier.py:73-75 inside try). Three rows at `04:40:28` for
  user `8436144812` = three delivered push messages.

**Admin alerts were the only broken part** — no `ADMIN_TELEGRAM_CHAT_IDS` (backend)
and no `ADMIN_CHAT_ID` (notifier) in `.env`, hence `no_admin_chat_ids`. Set both to
`8436144812` (the id already receiving pushes, taken from `data/salebot.db`).
Verified: `POST /admin/test-alert` → `{"sent": true, "reason": "ok", "sent_to": [8436144812]}`.

**miniapp**: never built (`no dist`, `no node_modules`). Built with
`systemd-run --unit=miniapp-build` → `dist/index.html` + assets (vite, 1m 47s).
`GET /` of the backend now serves it (`MINIAPP_DIST` mount). Public HTTPS is still
absent: `https://vpn.trikiman.shop/` → **525** (Cloudflare cannot reach origin TLS)
and nginx on :80 answers 301 for `/`. `WEB_APP_URL` set to the live
`https://vkusvillsale.vercel.app` so the bot's "Открыть" button no longer points at
the `t.me/your_bot_name/app` placeholder.

**Needs the operator:** the domain/TLS decision (Cloudflare 525) — serving the
miniapp on its own HTTPS host means DNS/CF changes on his side. Nothing else blocks.

## Session

**Last session:** 2026-11-16 (v1.30: phases 94, 95, 97 closed; Phase 96 soak running)
**Stopped at:** soak in progress (168 h, verdict 2026-11-23); instrumentation + daily cron live
**Resume file:** None

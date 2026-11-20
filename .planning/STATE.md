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

## 2026-11-20 15:00 MSK — GREEN IS BACK, and the deadlock is explained

First green items since 02:03 MSK: `Found 3 green products`, soak recorded `live 1` then
`live 3` with `ok`. The deadlock was a loop of three separate defects, each hiding the next:

1. **The cart could never become non-empty.** `/cart/` exposes no add-to-cart control at
   all for this account (`Seed item: no_button_found` survived 5 polls of 4 s), so the seed
   step had nothing to click. VkusVill shows green prices *only inside a non-empty cart* →
   empty section → its own "Зелёных ценников сейчас нет" banner → `source_empty` → snapshot
   wiped to 0. The banner was true, but it was caused by our own empty cart.
2. **The cart's emptiness was decided from wording, not from the DOM.** The log said
   `Seed item added — cart is now non-empty` and the next cycle said
   `{'empty': True, 'reason': 'empty_text'}`: "Корзина пуста" also lives in hidden
   templates, and it was checked before the item nodes. So the scraper re-seeded every
   cycle instead of proceeding.
3. **The seed had to come from the catalogue.** `/goods/ovoshchi-frukty-yagody-zelen/`
   always has real cards with real buttons; `_seed_from_catalog()` clicks one with the full
   pointer/mouse sequence and returns to `/cart/`.

Fixes in order: `ba16e10` (poll + real click for the in-cart seed), `2440ab0`
(`_seed_from_catalog`), `bd3605e` (DOM-first emptiness check).

**New defect spotted in the same breath, not yet fixed:** the green item served by the API
is `Лук репчатый 55 было 55` — `oldPrice == currentPrice`. A markdown price equal to the
old price means the old price is being read from the wrong field on green cards (the same
class of bug as the deleted `current / 0.6` heuristic). Worth checking before the UI shows
a meaningless "−0%".

## 2026-11-20 14:05 MSK — correction: the address EXISTS; the cards were empty skeletons

Two of my own conclusions were wrong, and the new diagnostics overturned both.

**1. "The account has no address" — false.** The deployed dump prints the header text:

```
Delivery address: opened_delivery_and_payment|header=...сногорск, Подмосковный бульвар, 11
```

The tech account has a saved, selected delivery address (Krasnogorsk, Podmoskovny bulvar 11).
Everything I built on "no address" was chasing the wrong fault; the `no_saved_address`
status came from scanning the SLOT picker, which legitimately contains no address.

**2. "The cards have no add button" — false.** Scoping the diagnostics to the green
section showed what the four `.ProductCard` nodes really are:

```
Green section cards in scope: 4
card ' ' has_add_text=False / controls=[]
```

They are **empty skeleton placeholders**. `no_button: 4` was the scraper clicking on four
empty boxes. Counting `.ProductCard` never proved anything.

Fixes shipped for this: `_wait_for_green_cards()` (scrolls the lazy section into view,
polls 25 s for cards with text > 8 chars) and, before it, `ac4e386` — UI labels contain a
non-breaking space (`Доставка и\xa0оплата`), which silently broke my own `norm()`.

**Current, honest state of the green cycle (14:00 MSK):**

```
⚠️ Green section still shows no rendered cards after 25s — the section is empty, not just slow
⚠️ VkusVill explicit empty banner detected — wiping stale snapshot (0 → 0)
Found 0 green products
```

So the section really is empty for this account right now, and VkusVill's own banner says
so — `source_empty` is *legitimate* in this cycle, not a scraping artifact. The scraper now
distinguishes "slow" from "empty" instead of blaming a missing button.

**What is still unexplained and is the next real question:** the account is in Krasnogorsk
while the sale assortment is regional. Whether greens exist for this address at this hour is
unknown — the only way to tell is to compare the same address in a browser. That is the
next check, and it needs no SSH.

## 2026-11-20 13:00 MSK — ROOT CAUSE: the tech account has no delivery address

Proof, not inference. New log line from the deployed fix:

```
[GREEN] Delivery address: no_saved_address
```

And the mechanism, verified on the live site in a real browser:

* The add-to-cart control is `button.CartButton__content--add.js-delivery__basket--add`
  inside `div.ProductCard__cartFooter` / `div.CartButton[data-product-id]`.
* With **no delivery address** that button is present, visible and enabled — and does
  nothing. Both a JS `.click()` and a real coordinate click (trusted CDP input) leave the
  wrapper class at `CartButton--notAdded`; nothing lands in the cart.
* The header keeps showing "Выберите способ и время доставки" and the address modal says
  "Адрес не найден".

So the chain that has been costing us the whole day is:

`no delivery address` → add-to-cart impossible (even for the ordinary seed item, which is
why `Seed item: no_button_found`) → cart is empty → VkusVill renders its
"Зелёных ценников сейчас нет" banner → `classify_empty_state()` sees `empty_explicit=True`
→ snapshot wiped to 0 with `source_empty` → the UI honestly reports "ВкусВилл ничего не
уценил" while the real cause is a missing address.

**Consequence for phase 96's acceptance criteria (must be rewritten):** `source_empty` is
NOT proof of an empty shelf while the cart cannot be filled. Any `source_empty` produced in
a cycle where the seed item failed to add must be treated as a scraping failure, not as a
genuine empty state. This is the difference between a real 168-hour proof and a formal one.

Fixes shipped today (each committed and deployed through the webhook):

| commit | what it fixed |
|---|---|
| `aa63271` | slot picker was opened and abandoned; added `_select_slot_after_open` |
| `43a64f2` / `a903752` | "slot already chosen" was a false positive (tabs, "В корзине") |
| `317ef17` | picker opens from the header control, not `.js-delivery-slots-load` (4 wrong modals) |
| `c307a88` / `10e3d49` | `_diagnose_no_button_cards` — and scoped to the green section |
| `419c754` / `f5b4890` | click matches the label on any element, full pointer/mouse sequence |
| `523a8ea` | `_ensure_delivery_address` — pick a saved address before the slot |

**Open:** the account needs an address added once. The modal's "Добавить новый адрес" form
uses Yandex autocomplete — typing an address string alone does not resolve it ("Адрес не
найден"), and the input disappears between steps, so this needs a proper suggestion-pick
flow (open `HeaderATDToggler__Link` → «Добавить новый адрес» → type → click the suggestion
→ «Выбрать»/«Сохранить»). Until that lands, green stays 0 no matter what the slot does.

## 2026-11-20 12:20 MSK — the cart is broken site-wide for the tech account

Fixing the slot exposed a wider fault. Latest cycles (12:04–12:14 MSK):

```
Step 1.5 delivery slot: open_attempt_not_found   (header control not found this run)
Cart check: empty (no_items_no_clear)
Step 2.5: Cart is empty — adding seed item...
Seed item: no_button_found                       <-- a NORMAL product cannot be added
Inspected: live_count=0 empty_explicit=False
Green section: found 0 green items
Button state: not_in_dom
```

`Seed item: no_button_found` is the important line: an ordinary seed product also cannot
be added, so this is not a green-section problem — add-to-cart does not work for the tech
account at all. Earlier diagnostics proved the control exists and is not disabled
(`kinds=['a','a','div','div','button','span']`, `buttons=['В корзину', ...]`), so the
click itself is what fails. The prime suspect is that `.click()` on those nodes does not
reach VkusVill's handler — a synthetic CDP click (pointerdown/mouseup/click sequence on
real coordinates) is the next thing to try.

The diagnostics function was also wrong on its first version (it scanned every card on
the page and reported cart items), now fixed to use the green-section scope (`10e3d49`) —
it simply has not run since, because the section reports 0 cards.

Egress is worse than before: `urnetwork-ru ... failed: [Errno 101] Network is unreachable`,
pool 0 nodes with `streak=82`, and SSH via 127.0.0.1:10870 still refused three times, so
none of this could be checked on the box itself.

## 2026-11-20 11:55 MSK — the 8-hour green=0 is a broken cart, not an empty shelf

Green has been 0 since **02:03 MSK**, and the API kept saying `source_empty` (VkusVill's own
"Зелёных ценников сейчас нет" banner). The banner is real but it is a **consequence**, not
proof: the scraper's tech account could not put anything in the cart, so the banner was
inevitable. Log evidence from the failing cycles:

```
cart_empty_before_seed -> Seed item: no_button_found -> Button state: hidden:4
Inline add-to-cart: {added: 0, no_button: 4}  (and again on retry)
```

Three defects found and fixed in `scrape_green.py` (each deployed via the webhook):

1. **`aa63271`** — `_ensure_delivery_slot` opened the picker and returned without choosing
   a slot; the very next call, `_close_delivery_modal`, pressed Escape and closed it. Added
   `_select_slot_after_open()` (rescan, pick a time-like slot, confirm).
2. **`43a64f2` + `a903752`** — the "slot already chosen" test was falsely positive:
   `[class*="Slot"][class*="active"]` matches filter tabs, and `/в корзин/i` matched
   "В корзине". Now it needs a visible "В корзину" button anchored to its full text inside
   a `.ProductCard/.HProductCard/.BasketItem`.
3. **`317ef17`** — `.js-delivery-slots-load` does NOT open the picker (it left four
   unrelated modals: оплата / подарочные карты / показать все). What opens
   "Мои адреса / Доставка / Самовывоз" is the header control "Выберите способ и время
   доставки" — verified in a live browser. It is tried first now.

**Result of the fixes (live logs, 08:43 UTC):**
`After opening picker: modals=66 delivery_candidates=20` →
`Delivery slot pick (after open): picked:Ближайшие 40 минут` →
`confirm: confirmed:Применить` → `Slot retry after hidden buttons: selected_after_open`.

**Still broken:** the four cards keep reporting `no_button: 4` even with the slot selected,
so `basket_recalc` returns nothing and the snapshot is wiped. Cause unknown — out of stock,
not deliverable to this address/slot, or different markup. Commit `c307a88` adds
`_diagnose_no_button_cards`, which dumps each card's text, its visible buttons and
out-of-stock / not-deliverable / notify-me flags, so the next cycle answers that instead of
inviting another guess.

**Also degraded:** `basket_recalc via urnetwork-ru failed: [Errno 101] Network is
unreachable`; VLESS pool 0 nodes (streak 80); SSH through 127.0.0.1:10870 is refused
(`Connection closed by UNKNOWN port 65535`, three attempts), so all of this is HTTP-only.

## 2026-11-20 08:05 MSK — history does not inflate; still waiting for green

Checked that the price history is not creating a fake "sale" on every cycle (a real risk
with a scraper running every few minutes). Session dates on the same products, 24 h apart:

- yellow 72242: **6 sessions**, dates 2026-11-16, 15, 14, 13, 11, then 2026-09-11 — distinct
  days, prices 258–430 ₽, windows 422 min+, no duplicate from today;
- red 56687: 3 sessions, 2026-09-16 / 2026-08-16 / 2026-07-26;
- green 46052: 1 session, 2026-11-15, 685 → 1268 ₽.

So each appearance is recorded once, not once per scan. Green is still `source_empty` at
08:01 MSK (greenLive 0, 165 products: red 43 / yellow 122, `updatedAt 07:58:31`), which is
the normal nightly state; the next real check is the ~10:05 MSK appearance window.
Soak: 517 cycles, 470 ok, 90.91%, **91.8 h**, `false_zero_cycles 0`, 8 known gaps.

## 2026-11-20 07:30 MSK — data-quality check, and a trap in my own measuring

Night product set (168 items, red 43 / yellow 125, green empty as expected):
**0 without currentPrice, 0 without oldPrice, 0 non-numeric prices, 0 with stock=0.**

My first pass reported "22 items with oldPrice <= currentPrice" — **that was my bug, not
the data**: `/api/products` returns prices as **strings** (`"66"`, `"110"`), so lexicographic
comparison says `"110" <= "66"` is true. Re-checked with `float()`: **0 inverted pairs**.
Recorded the rule so it stops recurring: in this API `currentPrice`/`oldPrice` are strings
and must be compared numerically.

## 2026-11-20 06:00 MSK — verified the empty-green night is explained in the UI

The night-time `green: 0` must not look like a broken site, so I followed it all the way
to what a visitor actually sees. The production bundle served by Vercel
(`assets/index-opH5fajR.js`, 270 776 B) contains every message needed:

- `Сейчас нет зелёных ценников — ВкусВилл ничего не уценил` — shown when
  `greenEmptyReason === 'source_empty'`, i.e. the honest night case;
- `Зелёные ценники не загрузились — проверяем подключение` — the real-failure wording;
- `Обновляем зелёные: счётчик N, в списке M` — the counter/list drift bar added earlier;
- `greenCountMismatch` — the API field behind it.

`gsd-tools validate health`: **0 errors**, warnings unchanged (W007×42 is the known
validator artefact — it reads only the current milestone section, so completed phases
named as ranges in the milestone list can never satisfy it; W019×3 stray planning notes;
W009/W018/W005 historical). Nothing here blocks phase 96.

Next planned step is not a code change: green appears around 10:05 MSK per the history
forecast, so the next real check is that `live` climbs above zero and the site shows
real green cards with the counter matching the list.

## 2026-11-20 05:50 MSK — yellow dropped from the site for 32 min; threshold fixed

Spotted while re-checking the blocker: `/api/products` returned **43 products instead of
165**, and `sourceFreshness.yellow` said `ageMinutes 32.2, isStale true`. Cause: yellow
is a paginated crawl (48 → 72 → 96 → 144 items, each page a fresh DOM read) and one
pass legitimately ran past the 30-minute threshold, so the API stripped **all 122 yellow
cards** while the file itself was healthy. Recovery confirmed on its own minutes later:
165 products, yellow `age 3.0`, `dataStale false`.

Fix (`544b3e1`): `DEFAULT_STALE_THRESHOLDS_MINUTES` yellow **30 → 45**, matching green —
long enough for one paginated pass, short enough to still catch a dead scraper. Live
after deploy: thresholds `{green: 45, red: 30, yellow: 45}`, 165 products.

Two more honest notes from the same window:
- green was 0 and that was correct: the log shows `VkusVill explicit empty banner
  detected — wiping stale snapshot (0 → 0)`, i.e. the site itself says there are no
  green items right now (night; history forecasts appearances around 10:05 MSK);
- while editing the threshold dict I first produced a **duplicate `"yellow"` key**
  (the later 30 silently shadowed my 45). Caught immediately, and a test now asserts
  the keys are unique so this cannot pass review again.

## 2026-11-20 05:05 MSK — blocker CLEARED: the 502 was transient, not a firewall

Re-checked as asked. Now, three consecutive calls:

```
https://vkusvillsale.vercel.app/api/products → 200, 84380 B, 0.8-4.5 s
updatedAt "2026-11-20 05:04:27", 165 products
external reachability of :80 from 10 nodes → 2xx: 9, timeout: 1   (was 1 / 9)
```

So the origin was reachable again from almost everywhere — the earlier `1/10` reading
caught a transient routing/stall window on Oracle AMS, not an ingress rule. No firewall
change is needed; the OCI/SSH ask is withdrawn (SSH itself is still dead, but it is no
longer blocking anything right now).

Also verified while the site was up: `greenLiveCount 0, greenListedCount 0` is NOT a
suppressed or false zero — `greenEmptyReason: "source_empty"`, `greenMissing: true`, and
`sourceFreshness.green` says `exists: true, ageMinutes 11.5, isStale: false`. Last six
cycles recorded `live=0` at 01:20–01:53 UTC, which matches the normal daily pattern
(the history page's forecast puts green appearances around 10:05 MSK). The API is telling
the truth: there are no green items right now, and it says why.

Soak at the same moment: 497 cycles, 450 ok / 47 failed, **90.54%**, `false_zero_cycles 0`,
**88.8 h** recorded, 8 gaps (all known — no new one since #8), last ok 11.5 min ago.

## 2026-11-19 21:40 UTC — [CLEARED] the public site loads, its API returns 502

The Vercel front is up, but it cannot reach the origin, so the site is empty for any
visitor. Measured, three attempts each:

- `https://vkusvillsale.vercel.app/` → **200**, 2693 B, bundle `assets/index-*.js` present;
- `https://vkusvillsale.vercel.app/api/products` → **502**,
  `ROUTER_EXTERNAL_TARGET_CONNECTION_ERROR` (122 B error page);
- `http://152.70.58.201/api/products` through our SOCKS tunnel → **200**, data fresh
  (soak recording 462 cycles, last ok minutes ago).

External reachability of the origin, checked from 10 nodes worldwide
(check-host.net, `check-http`): **1 node got a 2xx, 9 timed out**; an earlier 4-node run
gave Indonesia 301 and Hong Kong / Slovenia / Vietnam timeouts. So port 80 on the
origin is reachable only from part of the internet — that is why Vercel's edge fails.
Our own access works because it goes through the xray tunnel (443), not port 80.

Regression window: on 18.11 01:25 MSK the same Vercel `/api/products` returned 200 with
183 products, so this broke between then and now. Candidate causes, none provable
without shell access: an nginx/iptables allow-list change, or an Oracle Security List
rule restricting ingress on 80. **Needs server access (SSH is currently dead:
`empty-banner` through SOCKS) or the OCI console.**

## 2026-11-19 21:12 UTC — price history audited across all three tiers

`GET /api/history/product/<id>` verified on one product of each colour, live:

- green 46052 (Monini): 1 session, 685 → was 1268 ₽ (−46%), forecast next Sun 10:05,
  confidence 20% (only one appearance so far — honest, not a bug);
- red 56687 (tomato paste): 3 sessions, 66–97 ₽, forecast 20:55, confidence 20%;
- yellow 72242 (turkey thigh): 6 sessions, 258–384 ₽, forecast 23:25, confidence 100%.

`product`, `prediction` (day pattern, hour distribution, avg window, avg discount),
and per-session rows with price/old_price/discount/window all present. Note: the
history endpoint is `/api/history/product/{id}` — `/api/price-history/{id}` is 404
(my first probe; the endpoint name is easy to mix up, the data is fine).

Soak at the same moment: 462 cycles, 418 ok / 44 failed, 90.48%, `false_zero_cycles 0`,
84.0 h recorded, last ok 4 min ago; no new gaps since #8 (still 8, all known).

## 2026-11-19 00:10 UTC — pool refresh re-run, and an API-contract spot check

Manual `POST /admin/proxy-refresh` executed for real (log, not just the 200):
`00:01:55 Fetching VLESS list` → `00:05:48 Candidate-probe outer timeout reached;
continuing with partial pool` → `Refresh produced no admitted nodes; pool unchanged`
→ `Empty refresh streak=15 — backing off 30 min`. So the pool being 0 is the free-list
reality (231 hosts quarantined, none admitted: datacenter egress gets the VpnVill
VPN-page), not a stuck job. Green traffic keeps flowing over URnetwork + the static
VLESS node; `vless ok 200 3.91 s`, `urnetwork ok 200 7.5 s`.

Contract spot check: `/api/products` returns 13 fields per product; the miniapp reads
11 product fields, all present. My grep flagged `favKey`/`label` as missing — false
alarm: those belong to filter entries (`group:`/`subgroup:` rows built in App.jsx),
not to products. Same class of mistake as the earlier `discount: None`; the lesson
holds — verify the field's owner before calling it a defect.

## 2026-11-18 23:26 UTC — `/admin/status` scrapers block fixed

Was: every scraper field `None` (the dict is filled in the backend process, scraping
runs in the scheduler service) — read by anyone as "скрейперы не запускались".
Now: back-filled from `cycleState`, verified live right after deploy:

```
green    → 2026-11-18T23:22:10 | OK (data updated)
red      → 2026-11-18T23:23:14 | OK (data updated)
yellow   → 2026-11-18T23:25:11 | OK (data updated)
merge    → 2026-11-18T23:25:34 | OK (data updated)
notifier → 2026-11-18T23:25:34 | OK (notifications run)
```

5 of 8 keys filled (`login`, `categories`, `catalog_discovery` are not part of the
cycle state and stay empty by design). Commit `0ffafc0`, 3 tests, suite
**326 passed / 2 skipped**. The first admin call during the deploy returned 502 — that
was the backend restarting; the next one answered with the filled block.

## 2026-11-18 22:55 UTC — hangs eliminated, remaining failures are plain errors

Last 20 cycles: **0 SIGKILL** (the 45 s `page.evaluate` deadline + 90 s navigation
deadline hold), 2 failures total — `22:30 exit=1 dur=518 s` and `22:34 exit=1
dur=234 s`. Those are ordinary errors (probe timeout → browser path), not hangs:
`[RED]/[YELLOW] VkusVill probe failed: timed out - continuing with browser scraper`.
Soak: 320 cycles, 295 ok / 25 failed, **92.19%**, `false_zero_cycles 0`, 61.8 h.

`/admin/status` exposes `scraper_status` all-empty because that dict lives in the
backend process while scraping runs in the scheduler service — the live truth is
`cycleState` (currently `overall_status: healthy`, all three sources `ok`). Worth
fixing later so nobody reads the empty block as "scrapers never ran".

Pool: `size 0`, `last_refresh_at 11:50`, backoff active; `xray listening: true`,
breaker `closed`, and `/api/admin/egress-probe` reports `vless ok 200 3.91 s` +
`urnetwork ok 200 7.5 s` — traffic has a working path even with an empty pool.

## Realtime + auth audited 2026-11-18 21:55 UTC

- `GET /api/stream` (SSE) works: a 35 s listen produced `: keepalive` at ~30 s, and
  `event: update` fires when `proposals.json` mtime changes (verified in source:
  mtime poll every 2 s, keepalive every 15 ticks). My first 12 s probe returned
  nothing — that was the probe being shorter than the keepalive interval, not a fault.
- `GET /api/favorites/<user_id>` returns **403** without Telegram `initData` — the
  expected auth behaviour, not a defect; the payload would leak another user's
  favourites otherwise.
- `/api/products` and `/api/new-products` → 200.

## 2026-11-18 21:05 UTC — 7th gap closed by itself; the silence class is now bounded

The cron reported a genuine incident: two runs killed by the silence watchdog at
**1027 s** and **864 s**, both right after `Loaded 48/48 cookies via CDP`, opening
gap #7 (05:12 → 06:21 UTC, 69.4 min). It closed on its own with the next good cycle;
since then 20+ consecutive `ok` and uptime climbed back to **92.46%**
(305 cycles, 282 ok, 23 failed, `false_zero_cycles 0`, 59.9 h recorded).

Root cause of that silence: `_js` called `page.evaluate` with **no deadline**, and the
420 s watchdog only fires on silence — one stalled CDP round-trip therefore looked
like a dead cycle. Fix (`ed58274`): `_js` wraps `page.evaluate` in
`asyncio.wait_for(JS_EVAL_TIMEOUT_S=45)`, and `TimeoutError` joins
`_is_dead_ws_error` so `_safe_js` re-acquires a handle and retries within its
3-attempt budget instead of dying on the first timeout. 3 tests; suite 323 passed.

Side note from the logs: the dynamic pool has been empty for ~4.7 h
(`ensure_pool() returned 0 nodes`, backoff `streak=9`, 30-min interval), so all green
traffic rides URnetwork. That is the known free-list limitation, not a new regression.

## 2026-11-18 06:00 MSK — Vercel build failure caught and fixed (lesson)

Committing the whole local `miniapp/src/App.jsx` (commit `1f2dbc4`) took the Vercel
deploy down: this working copy has drifted from the repo, so the file carried
`import { fetchProducts } from './api'` while `miniapp/src/api.js` in the repo exports
only `getAuthHeaders`. Vercel build → **failure**.

Recovery: reverted (`fb1b1a2`), then re-applied only my 17 added lines on top of the
**repo** version, and verified by building the repo tree in a detached worktree
(`git worktree add --detach ... && npm ci && npx vite build` → `index-opH5fajR.js`).
Deploy `61b7bd1` → **success**, and the site serves `assets/index-opH5fajR.js`.
`GET /api/products` through the front now returns `greenLiveCount 1,
greenListedCount 1, greenCountMismatch null`.

Rule going forward: never `git add` a whole file from this drifted local tree —
diff first, apply only the intended lines, and prove the build on the repo tree.

## 2026-11-18 05:05 MSK — green counter vs green cards fixed (`05ddf63`)

Caught a live contradiction: `/api/products` said `greenLiveCount: 4` while the
payload carried **one** green card (04:55 MSK). Cause: `greenLiveCount` is stamped
into `proposals.json` at merge time, the cards come from that same payload, and a
green scrape landing between merge and request lets the counter run ahead.

Fix: the response now carries `greenListedCount` (cards actually present) and
`greenCountMismatch` (counter minus cards, `null` when they agree or either is 0).
Verified after deploy: `greenLiveCount=1, greenListedCount=1, mismatch=None`.
3 tests; suite 320 passed / 2 skipped.

Also observed on the same pass: **the VLESS route is alive again** —
`/api/admin/egress-probe` → `vless ok, status 200, 2.99 s` (was `timeout` all
night), `urnetwork ok, 12.32 s`. Pool still reports 1 node, so health stays
`degraded` on `pool_below_min_healthy:1_lt_5`, but traffic no longer depends on
URnetwork alone.

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
**Stopped at:** soak in progress — **false zero #1 at 20.11 05:12:12 UTC** pushes the readable date to **2026-11-27 08:12 MSK**; was 2026-11-26 09:18 — gap #8 on 19.11 04:54-06:18 was post-fix and pushes the window — the window must clear the 18.11 gap, see 96-SOAK.md «Date correction»); instrumentation + daily cron live
**Resume file:** None

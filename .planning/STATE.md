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

## 2026-11-27 18:55 MSK — exit 1 при «мало, но не пусто» вылечен в коде (деплой после 07:10)

За 168 ч 7 упавших циклов, из них **три — с товарами** (`12:15 live=28`, `12:20 live=28`,
`16:24 live=34`). Прогон отрабатывал, но уходил с кодом 1: расхождение >10 % с бейджем
попадало в ветку «сохранить старый снимок», а она валила цикл безусловно. Пользователь всё
время видел нормальный снимок, страдал только `uptime_pct` (94.6 % в отчёте 18:35).

`classify_green_count_mismatch` (`66c124e`) делит случаи: писать новый список — если он
полный или лучше лежащего; держать снимок и остаться exit 0 — если снимок младше часа и
сам содержит ≥10 позиций (не-фатальная пометка `count_mismatch_preserved` в
`green_last_failure.json`); держать снимок и падать — только если скрап почти пустой или
снимок протух. 8 тестов на классификатор; полный прогон 540 passed / 1 failed (старый
флейк `test_vless_xray` на temp-файле, к правке не относится).

**Деплой отложен, и это осознанно:** чтобы фикс заработал, нужен рестарт бэкенда, а до
07:10 28.11 (выход последнего гэпа из окна) любая дырка обнуляет неделю. Ставим **после
приёмки в 09:05**, не раньше. До тех пор живые циклы продолжают идти старым кодом —
поведение не менялось.

## 2026-11-27 18:05 MSK — критерий 4 приёмки был недостижим by construction; исправлен

Живой отчёт (`hours=168&tail=200`, 17:13 MSK): 905 циклов (854 ok / 51 failed), uptime
94.36%, `false_zero_cycles: 0`, `gap_incident_count: 3`, `hours_recorded: 167.8`.

**Дефект.** `phase96_acceptance.py` требовал `hours_recorded >= 168`, но `hours_recorded`
— это span между первой и последней записью в окне (`backend/green_uptime.py:197`), а не
прошедшие часы. Последняя запись всегда на минуты старше `now`, первая — на минуты позже
`window_start`, поэтому у здоровой недели span упирается в ~167.8 и 168 не достигает
**никогда**. Приёмка 28.11 провалилась бы на часах, а не на соаке; крон 08:17 списывал это
в «expected FAIL». Каждый дневной отчёт с 22.11 нёс `hours_recorded: 23.7–23.8` в 24-часовом
окне по той же причине — это был один и тот же баг, который никто не прочитал как баг.

**Фикс** (`9f99e38`): `MIN_HOURS = 168 − 0.75`, допуск = собственный 45-мин порог гэпа —
дырка длиннее 45 мин уже считается `gap_incident_count`, поэтому концевые остатки короче
порога нельзя считать дважды. Тесты: 167.9 PASS / 166.9 FAIL, 7/7 зелёных.
Живой прогон после фикса: **3 PASS / 1 FAIL**, единственный фейл — `gap_incident_count == 3`.

**Куда деваются 3 гэпа — правило `from_ts + 168 h`, а не `to_ts + 168 h`.** Гэпы считаются
по `ok`-записям внутри окна (`backend/green_uptime.py:147`), поэтому гэп исчезает, когда из окна
выходит последний хороший цикл ПЕРЕД ним. Проверено на живых данных: гэп #1 (`from_ts` 20.11
17:33) ещё считался в 17:13 и исчез в 18:15 — `gap_incident_count` **3 → 2**, ровно по правилу
`from_ts`. Значит остаток: 45.3 мин → 27.11 **22:50**, 97.7 мин (#11) → 28.11 **07:10**.
Самая ранняя честная приёмка — 28.11 **07:10 MSK**, т.е. крон в 09:05 имеет запас 1 ч 55 мин,
а не 18 минут, как считалось по `to_ts`. Расписание крона не трогал. Рестарт бэкенда до 07:10
запрещён — это ровно та дырка, которая уже четыре раза обнуляла неделю.

**Риск завтрашнего batch-proof в 08:15 проверен цифрами, а не на глаз:** за последние 200
циклов (26.11 04:31 → 27.11 18:00) интервал между записями — медиана 10.8 мин, p95 17.6,
**максимум 21.1 мин** при пороге гэпа 45 мин (двукратный запас). Утренние циклы 26.11 и
27.11 в 08:05–09:56 — все `ok`, самый длинный 945 с при 156 живых карточках. Поэтому расписание
крона не трогал: доказанной опасности нет.

**Отложено до закрытия фазы (нужен деплой, значит рестарт):** из 7 упавших циклов за 37 ч три
пришли с товарами — `27.11 12:15 live=28 exit=1`, `12:20 live=28 exit=1 empty=ok`,
`16:24 live=34 exit=1`. То есть прогон отработал, но вышел с кодом 1 и засчитан в
`cycles_failed`; это занижает `uptime_pct`, но **не** гейтит приёмку (гейты — гэпы и false zeros).
Правится в exit-пути `scrape_green.py` после 28.11, не раньше.

## 2026-11-27 08:15 MSK — мульти-батч add-to-cart подтверждён на живом модале (128 карточек)

`/admin/logs?n=300` (socks5h://127.0.0.1:10870, `X-Admin-Token`) показал не одну партию,
а **семь** подряд — то, чего не было ни разу с фикса 21.11:

```
[GREEN] Modal loaded: 128 cards
[GREEN] Step 3.1.3: Adding 128 items to cart...
[GREEN] Green cards rendered: 24 (after 0.0s)
[GREEN] Batch 0-10: added 10 (running total 10)
[GREEN] Batch 10-20: added 10 (running total 20)
[GREEN] Batch 20-30: added 10 (running total 30)
[GREEN] Batch 30-40: added 10 (running total 40)
[GREEN] Batch 40-50: added 10 (running total 50)
[GREEN] Batch 50-60: added 10 (running total 60)
[GREEN] Batch 60-70: added 10 (running total 70)
```

`Batch 10-20` и далее виден впервые — многошаговый цикл `_add_green_cards_to_cart`
работает на объёме, а не только на единственной партии `0-4`, как 21.11 22:25.

Честная оговорка: строки-завершения `Added N/N items to cart` в окне лога нет —
сразу после `Batch 60-70` (running total 70 из 128) прогон упал на
`ConnectionError: Connection closed` (`scrape_green.py:2176`, `browser.get`), и цикл
перезапустился. Подтверждён **механизм** мульти-батча (>=2 партии на реальном модале),
но **не** полное добавление 128/128 в этом прогоне. `Inline add-to-cart` отсутствует —
путь шёл через модальную секцию, а не инлайн.

## 2026-11-22 17:35 MSK — 14 тестов, которые вообще не собирались, теперь зелёные; 7 падений были протухшими ожиданиями, а не багами

The workstation had no `python-telegram-bot`, so five test modules died at import with
`ModuleNotFoundError: No module named 'telegram'` (4 collection errors + 10 setup errors).
Installed the two missing runtime deps into an out-of-tree dir —
`python3 -m pip install --target ~/.hermes/cache/testdeps python-telegram-bot python-multipart`
(nothing installed into Hermes' own interpreter, nothing written to `E:` — it has 1.1 GB left,
`C:` has 52 GB) — and ran with `PYTHONPATH=~/.hermes/cache/testdeps`.

That immediately exposed **7 real failures**, all of them stale expectations rather than bugs:

| test | expected | shipped reality |
|---|---|---|
| `test_build_source_freshness_default_thresholds_are_per_color` | green 45 / red 30 / yellow 30 | **45 / 45 / 45** since v1.30 |
| `test_..._yellow_stale_only_above_30` | fresh 29.5, stale 31 | 45-min budget → both fresh |
| `test_compute_empty_reason_all_stale_when_every_file_past_threshold` | 45 min age = stale | 45 == threshold, not past it |
| `test_health_deep_..._full_schema` | 8 top-level keys | snapshot grew `status_note`, `chronic_reasons`, `acute_reasons`, `acute` (27cb16b) |
| `test_stale_cycle_is_degraded_503` | 30 min age trips it | `_DEEP_MAX_CYCLE_AGE_S = 30*60` → needs > 30 |
| `test_three_failed_criteria_is_unhealthy_503` | 30 min counts as a 3rd reason | same |
| `test_stale_products_json_is_degraded_503` | 30 min age trips it | `_DEEP_MAX_PRODUCTS_AGE_S = 45*60` |

Fixed on the test side only — the code is the source of truth and the thresholds are a
deliberate v1.30 decision (yellow 45, red 45, `3485e0c` budgets, `27cb16b` split). Test-only
files cannot restart anything: the webhook pulls on every push to main but restarts only for
`backend/`, `bot/`, `config.py`, `vless/`, `database/`, `scrape_*`, `scheduler_service.py`
(`backend/main.py:6649-6664`).

Result on those five modules: **98 passed, 0 failed** (was `0 collected, 4 errors` +
`91 passed / 7 failed`). Then one more stale expectation surfaced in
`test_scrape_green_ws_recovery.py`: it asserted `_is_dead_ws_error(TimeoutError(...)) is False`,
while `TimeoutError` has been deliberately inside the dead-WS set since 2026-11-18 (a hung
evaluate is a dead tab). Split into two tests: unrelated errors → False, hung evaluate → True.

**Full suite on this workstation: `531 passed, 1 failed, 3 skipped, 0 errors`.**
The one red is `test_vless_xray.py::test_start_succeeds_when_port_opens` — `health_check()`
returns False here because the check is written for the Linux box, not Windows. Nothing to do
with v1.30.

**Environment rule for reproducing this (learned the hard way):** install only
`python-telegram-bot` + `python-multipart`, and **do not** install real `nodriver` into
`testdeps`. With real `nodriver` present the suite goes to `9 failed` — `test_green_recovery.py`
and `test_scrape_green_ws_recovery.py` guard their fake `nodriver` on the package being
*absent*, so importing the real one silently swaps their fixtures. Reproduce with:

```
python3 -m pip install --target ~/.hermes/cache/testdeps python-telegram-bot python-multipart
PYTHONPATH=~/.hermes/cache/testdeps python3 -m pytest tests/ -q
```

## 2026-11-22 16:05 MSK — acceptance arithmetic re-checked, and the margin is 5 minutes, not 168 hours

Ran the numbers against the live endpoint instead of trusting the phase note
(`green-uptime?hours=168&tail=200`, 200 cycles covering 21.11 02:43 → 22.11 13:15 UTC):

| criterion | now | at 2026-11-28 06:00 UTC |
|---|---|---|
| `false_zero_cycles == 0` | 1 (20.11 05:12 UTC) | window starts 21.11 06:00 → event 43 h outside |
| `gap_incident_count == 0` | 11 (last: gap #11 04:10→05:47:51 UTC 21.11) | window starts 21.11 06:00 → 12 min of air |
| `hours_recorded >= 168` | 148.2 | needs ~20 more hours; recorder starts 16.11 → fine |
| no gap after epoch | 0 | — |

`GAP_INCIDENT_MINUTES = 45` (`backend/green_uptime.py:36`), so a single failed cycle is not a
gap — only a hole wider than 45 minutes between two `ok` cycles is. Sixteen cycles failed in
that 200-cycle span (eight of them inside gap #11, plus 21.11 11:23, 11:32, 13:37, 21:28 and
22.11 04:52, 05:04, 08:54), and **none of them produced a gap** because the `ok` neighbours
stayed closer than 45 min.

**The risk, with a number:** after gap #11 the widest hole was **40.0 min** (22.11 04:47 →
05:27 UTC, two failed cycles in a row) and another 38.6 min on 21.11 11:11 → 11:50. That is
**5 minutes of headroom** to a new incident. Two failed cycles that happen to straddle a
15-minute gap will reset the whole 168 h window and push acceptance out by another week. So:
no deploys, no config changes, no manual scrape triggers before 28.11 09:00 MSK — every one of
them buys a few minutes of jitter for nothing.

## 2026-11-22 15:40 MSK — the morning checks did not run, because the LLM did not

Both Phase-96 crons fired on time and both died before touching saleapp:

| job | fired | status | error |
|---|---|---|---|
| `3dc7ab1ba33a` batch proof (08:15) | 08:15:31 | error | `No reply: every provider in the fallback chain kept failing over` |
| `894c7424bbbe` soak report (09:00) | 09:00:33 | error | same |

So the 08:27 MSK markdown day — the one with `live_count=184`, the biggest green
section seen since the batch fix — was never inspected, and `/admin/logs` (300 lines,
minutes only) had scrolled past it by the time I looked at 12:23 UTC. **Multi-batch
stays unproven.**

And it stays unproven on purpose: `184` live products does **not** prove 18 batches
ran. `_reveal_green_card_stock()` adds DOM cards to the cart and then rebuilds stock
from `basket_recalc`; `_merge_green_cart_data()` also pulls green items that were
already in the basket. A published count therefore mixes "added now" with "already
in cart", and only the `Batch N-M: added K` lines distinguish them. Those lines are
gone.

**Fix — evidence must not depend on a model being reachable.** Two deterministic
collectors, `no_agent`, no LLM in the path:

| job | schedule (MSK) | script | what it does |
|---|---|---|---|
| `9bedad3da8b0` | `*/3 6-11 * * *` | `~/.hermes/scripts/saleapp_batch_proof.sh` | tails `/admin/logs`, appends new `Batch`/`items to cart`/`Inline add-to-cart` windows to `.planning/phases/96-soak-and-uptime-report/batch-proof.log`, silent unless ≥2 distinct ranges appear in one window |
| `849ba2418e5a` | `5 9 * * *` | `~/.hermes/scripts/saleapp_soak_snapshot.sh` | appends one JSON line/day to `soak-daily.log` (cycles, ok, failed, uptime, false_zero, gaps, product counts) and prints a single line |
| `08440c65ff15` | once, `2026-11-28 09:05` MSK | `~/.hermes/scripts/saleapp_acceptance_check.sh` | runs `phase96_acceptance.py` + `green_soak_check.py` and prints `VERDICT: acceptance MET / NOT met`; exit 0/2. It never closes the phase itself — that stays a human/GSD step |

Both were executed by hand first: the batch collector exited 0 silently (no batch
lines in the current window — correct), the snapshot wrote
`cycles=143 ok=138 failed=5 uptime=96.5% false_zero=0 gaps=0 … green=32 red=55 yellow=118`.
The batch parser was additionally exercised on a synthetic three-range window
(`Batch 0-10/10-20/20-30`) → `distinct_ranges=3`, correct extraction.

**My own mistake, recorded:** at 15:24 MSK I fired `POST /api/admin/run/green` by hand.
It collided with the scheduler's own cycle and died with
`ConnectionError: Connection closed` on `browser.get('https://vkusvill.ru')`,
exit 1, `[GREEN] Failure report -> data/green_last_failure.json (unclassified)`.
One vCPU, one Chrome on 19222, one egress tunnel — a manual run during a cycle does
not test the scraper, it tests who wins the browser. No cycle was recorded as failed
(manual runs are not uptime cycles) and the published data stayed fresh
(`greenAgeMinutes` 12.8, `isStale: false`). Rule: **do not hand-trigger a scrape while
the scheduler is mid-cycle.**

Today's green curve is the normal markdown decay, not a regression: 184 (05:27 UTC) →
149 → 125 → 108 → 86 → 73 → 58 → 45 → 17 → 37 → 32, all `ok`.

**Multi-batch now has an offline proof too.** `tests/test_green_batched_windows.py`
(drives the real `_add_green_cards_to_cart` coroutine with a fake page that records every
evaluate): 25 cards → windows `(0,10) (10,20) (20,25)`, 100 cards → ten windows with no
hole and no overlap, one dead batch → the run continues and costs exactly its own ten
cards (`added 15`, `failed_batches 1`, `partial 1`), zero cards → no evaluate at all.
The earlier `test_green_batched_add.py` only asserted the loop *shape* via AST — a wrong
`end` or an early `break` would have passed it. Run: `4 passed in 4.71s`, and the pytest
output itself prints `Batch 0-10 … 90-100` plus `Batch 10-20 failed … continuing`.

**That test then cost nine unrelated tests, and I caught it by comparing against baseline.**
It injected a fake `nodriver` into `sys.modules` to make the import work and left it there
for the whole pytest session — `test_green_recovery.py` and `test_scrape_green_ws_recovery.py`
install their own richer stub and were silently overridden. Full run before the fix:
`10 failed, 444 passed, 3 skipped, 10 errors`. Fix: pop the stub (and the cached
`scrape_green`) right after the import, only if this module created it. After the fix, with
the same four ignores: **`2 failed, 452 passed, 3 skipped, 10 errors`**, and both remaining
failures reproduce with the new test file absent.

The remaining red is the workstation, not the code: the 10 errors are all
`ModuleNotFoundError: No module named 'telegram'` (no `python-telegram-bot` here, so any
test that imports `scheduler_service` can't even set up), the 4 modules skipped by
`--ignore` fail at collection for the same reason, and `test_vless_xray.py::
test_start_succeeds_when_port_opens` fails on its own (local xray start). Worth remembering
when reading the "396 passed" line from previous sessions: that number came from a
different selection, not from a greener tree.

## 2026-11-21 08:55 MSK — a big markdown day broke the green run five times, in two places

VkusVill put ~100 green tags up this morning (modal went 48 → 96 → 100 cards). The scraper
had been tuned for a handful, and one heavy `page.evaluate` blew the 45 s deadline — the
TimeoutError threw away runs that had already scraped the modal:

| time | duration | where it died |
|---|---|---|
| 07:17 | 301 s | `_add_green_cards_to_cart` (100 clicks in one evaluate) |
| 07:26 | 522 s | same |
| 07:44 | 475 s | same |
| 07:55 | 518 s | same |
| 08:02 | 399 s | same, `live=69` already scraped |
| 08:26 | 538 s | modal scroll evaluate, 98 products collected |

Because GREEN runs first, RED and YELLOW never executed: at 07:35 the API served green only
(`red` 34.9 min old, marked stale) while `red_products.json` was intact. The site showed 69
greens and nothing else.

Three fixes, all deployed:

1. `4e9ac8f` — clicks in batches of ten per evaluate, each batch guarded (a timeout costs ten
   cards, logs, re-acquires the page handle, continues).
2. `507e43a` — the modal scroll is guarded (logs `stopping the loader at N cards`, breaks) and
   `JS_EVAL_TIMEOUT_S` goes 45 → 90 s.
3. `dfb423a` — red staleness 30 → 45 min, matching green and yellow. A slow cycle is not a dead
   scraper; the price is that a genuinely dead red is noticed 15 minutes later.

First clean run after the fixes: `Found 26 green products`, `Dropped meaningless old price on
25 item(s)`, `Saved 26 products (live_count=26)` — the old-price guard is now confirmed in a
live log, which it never was before.

## 2026-11-21 09:50 MSK — health stopped crying "egress" every cycle

`/api/health/deep` had said `degraded` on every single check since 18.11: the VLESS pool is
empty (refresh admits 0 of hundreds of candidates, backoff streak 120) while all three scrapers
keep collecting through direct/URnetwork. That is standing debt, not a fault — but it was
reported identically to a real one, and gap #11 is the proof of what that costs: the daily
report blamed egress and both probes timed out, while the true cause was a JS deadline on a
100-card modal.

Two changes, both deployed:

- `27cb16b` — the snapshot now carries `chronic_reasons` / `acute_reasons` / `acute` /
  `status_note`. A pool-only reason list gives `acute: false` and
  `status_note: egress_debt_only`; a stale products file or a dead xray bridge stays acute.
  `status` keeps its documented OBS-02 meaning, so existing monitors are unaffected.
- `3485e0c` — the freshness budgets were shorter than one real cycle. GREEN alone takes
  570-800 s on a markdown day, then RED, then YELLOW: 18-20 minutes on 1 vCPU. 15-minute
  budgets meant `stale_cycle` + `stale_products` during healthy runs. Now 30 and 45 min
  (45 matching the tier staleness thresholds).

Live check after deploy: `status: degraded`, `status_note: egress_debt_only`, `acute: false`,
`reasons: ['pool_below_min_healthy:0_lt_5']` — the only remaining reason is the known debt.

The daily cron prompt now treats `acute: false` as non-alarm and alarms on `acute: true`.

## 2026-11-21 12:45 MSK — stability after the cascade, and what is still unverified

Eight consecutive `ok=True` cycles (11:25 → 12:36 MSK), `live` 30–37, durations **232–392 s**
against 300–571 s during the failures. No gaps since 08:47 MSK.

Honest gap in the evidence: **the batched click path has not yet been exercised in production.**
`/admin/logs` contains no `Batch …` lines today, because the green modal has been empty since
the morning markdown sold out (`Modal loaded: 0 cards`), so the add-to-cart step never runs and
greens come from the inline section. What IS proven:

- the failure itself (`TimeoutError` in `_add_green_cards_to_cart` / modal scroll) is gone —
  five runs died that way before 08:47 and none has since;
- cycle duration dropped out of the danger zone;
- 4 + 3 + 2 guard tests pin the batching, the guarded scroll and the 90 s deadline.

What is NOT proven: that ten-card batches add all 100 cards on a real 100-card markdown day.
That needs the next big markdown (typically morning). Until then this stays UNVERIFIED — do not
report the batching as "tested on the real thing".

## 2026-11-21 13:40 MSK — acceptance re-run mechanically, still 3 FAIL (as designed)

`python scripts/phase96_acceptance.py --proxy socks5h://127.0.0.1:10870` → exit 2:

```
cycles: 678 (607 ok / 71 failed), uptime 89.53%
[FAIL] false_zero_cycles == 0 — 1
[FAIL] gap_incident_count == 0 — 11
[FAIL] hours_recorded >= 168 — 121.6
[PASS] no gap after acceptance epoch — 0 post-epoch gap(s)
```

Three of the four criteria cannot pass before 28.11 09:00 MSK — the window still contains ten
pre-fix gaps, gap #11 and the diagnosed false zero #1. The fourth criterion (no gap after the
epoch) already passes, which is the part that actually depends on today's work.

This is a mechanism check, not a verdict: the script refuses to close phase 96 by design
(`Do not close phase 96`). Nothing here should be read as "almost done".

## 2026-11-21 17:20 MSK — declared features audited again, one line each

| Feature | Endpoint / signal | Result today |
|---|---|---|
| Products, three tiers | `/api/products` | 210 items: green 33 / red 55 / yellow 122, `dataStale: false` |
| Data integrity | same | 0 items without price, 0 with `oldPrice <= currentPrice` (float compare), 0 duplicate ids |
| Green not suppressed | `greenSuppressed` | `null` — greens really shown, not hidden by staleness |
| Price history | `/api/history/product/23074` | 22 sessions, DESC by date; `last_known_price 385.0` in **`product`**, not at the root |
| Prediction | same | 27.11 12:15, `confidence_pct 99`, avg window 185 min, advice "сейчас 0% — бывало 40%" |
| SSE | `/api/stream` | `: keepalive` (13 bytes) at ~30 s |
| Favorites auth | `/api/favorites/<id>` without initData | 403 — correct refusal |
| Frontend ↔ API | `check_frontend_matches_api.py` | exit 0, 214 = 214, age 6.7 min |
| Mini-app bundle | `vkusvillsale.vercel.app` | `assets/index-opH5fajR.js` |
| Telegram delivery | `POST /admin/test-alert` | last confirmed `sent: true` (not re-sent today — it messages the operator) |

Kept UNVERIFIED honestly: batched add-to-cart on a real 100-card modal (modal empty since
09:00), and the Telegram send for today. The morning cron has an explicit step for the batching.

## 2026-11-21 22:25 MSK — the batched add path ran in production (partly)

`/admin/logs?n=300` now contains the line the fix was written for:

```
[GREEN] Step 3.3: Button not in DOM but 4 green items found — adding inline...
[GREEN] Green cards rendered: 4 (after 0.0s)
[GREEN] Batch 0-4: added 4 (running total 4)
[GREEN] Inline add-to-cart: {'added': 4, 'no_button': 0, 'already_in_cart': 0, 'no_card': 0, 'disabled': 0}
[GREEN] Added 4/4 items to cart
```

Two consecutive runs did this. So `_add_green_cards_to_cart(batch_size=10)` is **no longer
unverified code**: it executes, it reports `running total`, and the inline section is the
source (not the modal, which stays at `Modal loaded: 0 cards`).

What this still does NOT prove: the multi-batch case. Here the whole job was one batch
(`0-4`, five card slots, four cards with buttons). The 100-card markdown that broke the run
on 21.11 morning needed ten batches; nobody has seen `Batch 10-20` or higher yet. Until a run
shows two or more batches, the 97-minute gap #11 fix is confirmed at one batch, not at ten.

Also learned: `/admin/logs` rejects `n=400` with HTTP 422 — the ceiling is `n=300`.

## 2026-11-22 00:15 MSK — an empty green section no longer kills the cycle

The 21:00 MSK run hit the exact shape that used to break everything:

```
[GREEN] Delivery slot pick (after open): picked:Ближайший 1 час Выбрано
[GREEN] Slot retry after hidden buttons: selected_after_open
[GREEN] ⚠️ Green section still shows no rendered cards after 25s — the section is empty, not just slow
[GREEN] Batch 0-4: added 0 (running total 0)
[GREEN] Green section cards in scope: 4
[GREEN]   card ' ' has_add_text=False   controls=[]   (×4)
```

Four empty skeletons, zero clicks, and the run finished anyway: RED and YELLOW executed, and by
00:02 the API carried all three tiers (24 green / 50 red / 100 yellow, `dataStale: false`).
Before the batching and the skeleton wait, this same shape threw away a finished run — and
because GREEN runs first, its failure looked like "red and yellow disappeared".

A batch returning `added 0` is therefore a normal outcome, not a failure: it means the section
was genuinely empty at that moment. Do not "fix" it by retrying clicks.

Still not observed: two or more `Batch` lines in one run (multi-batch on a real markdown).
Cron `3dc7ab1ba33a` at 08:15 watches for exactly that.

## 2026-11-22 01:45 MSK — nearly recorded a false defect about /admin/status

I read `scrapers.green.last_run = 2026-11-21T22:39:12` at 01:41 MSK and was about to write
"the scrapers have not run for three hours". The `ageMinutes` next to it said 3.9, which is
three **minutes**: `scrapers.*.last_run`, `sourceFreshness.*.updatedAt` and `cycleState.*_at`
are UTC, while `data.updatedAt` in the same JSON is Moscow time. `ageMinutes` is computed
server-side and is the field to trust; subtracting the printed timestamps by hand produces a
convincing false alarm.

Same response, two other traps: the key is `scrapers` (not `scraper_status`, which earlier code
did backfill), and `cycleState` refers to the last **full** cycle (22:32–22:42 UTC) — it is
legitimately older than the data files and must not be used as a freshness signal.

Recorded in the `saleapp` skill so the next reader (or the next cron) does not re-derive it.

State at the time of the check: green 25 / red 55 / yellow 117, `dataStale: false`,
`greenSuppressed: null`, health `degraded / egress_debt_only / acute: false`.

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

## 2026-11-21 05:20 MSK — how often the greens actually vanish now, measured

Counted the last 200 cycles (24 h) by `empty_reason`:

| Reason | Cycles | When |
|---|---|---|
| `ok` | 106 | — |
| `source_empty` | **92** | almost all inside two long runs |
| `unknown_empty` | 2 | the known false zero + one other |

The 92 empty cycles are not spread out — they sit in two runs: **02:10→08:12 (362 min)** and
**08:34→14:47 (373 min)**, i.e. the pre-fix deadlock (empty cart → hidden buttons → VkusVill's
own "no green tags" banner). After the 15:00 fix there are only two isolated cases:
21:20→21:38 (18 min) and 04:02→04:15 (13 min) — 31 minutes out of ~10 hours.

So the earlier "source_empty is legitimate emptiness" is true for the isolated cases and
**was not true for the two 6-hour runs**: those were our own deadlock wearing a legitimate
label. That is the trap in this design — `source_empty` cannot by itself distinguish "VkusVill
has nothing" from "we failed to seed the cart and VkusVill therefore showed nothing", and the
banner appears in both cases.

Practical consequence: watch for runs, not single cycles. A `source_empty` streak longer than
~45 min is a scraper symptom, not a shelf state.

## 2026-11-21 03:55 MSK — acceptance moved to 28.11 00:00 MSK — the old date could not pass

The previous epoch (27.11 05:12 UTC) was arithmetically impossible to satisfy. The acceptance
criterion is `gap_incident_count == 0` inside a 168 h window, and the newest gap (#10,
20.11 22:50→23:35 MSK) only leaves that window at **27.11 23:35 MSK** — 15.4 h after the old
date. Nothing would have been broken; the check would simply have failed on arithmetic.

New epoch: **2026-11-28 00:00 MSK (27.11 21:00 UTC)**, documented in
`scripts/green_soak_check.py` (`ACCEPTANCE_UTC`), `scripts/phase96_acceptance.py`
(`ACCEPTANCE_EPOCH`), the test that pins the moment, the daily cron prompt, and here.

Gap #10 is also recorded in `KNOWN_GAPS` **with an honest label**: its root cause is not
established (the log rotated before it was read); instrumentation was added afterwards
(`data/green_last_failure.json` → `failed:<reason>|found=N` in the journal). Recording it
classifies the alarm — it does not make it disappear: the gap still counts in
`gap_incident_count: 10` and still gates acceptance.

After the change: `green_soak_check.py` → **exit 4** (only known gaps inside the window,
nothing unexplained), `test_soak_check_gap_class.py` + `test_phase96_acceptance.py` → 15
passed.

## 2026-11-21 03:30 MSK — re-audit of the declared functions after the whole day of fixes

Everything below was checked against the live API just now, not read off old notes:

| Function | Evidence |
|---|---|
| Products API | 206 items: green **26**, red 57, yellow 123, `dataStale: false`, `updatedAt 03:19` |
| Mini-app vs API | `check_frontend_matches_api.py` → exit 0, identical counts, age 9.4 min |
| Price history | `/api/history/product/605` → **29 sessions**, `last_known_price 62.0`, `last_sale_type green`, `last_sale_at 2026-11-21T00:53` |
| Prediction | `predicted_at 2026-11-22T12:25`, `usual_time 12:25`, `confidence high (99%)` |
| Soak | last 7 cycles all `ok=True`, `live_count 25→26`, `last_ok` 17.8 min |
| Health | `degraded` **only** for `pool_below_min_healthy:0_lt_5`; `quarantined_count: 0` |

The one standing degradation is the VLESS pool sitting at 0 nodes; it does not affect the
scrapers because egress falls back to direct/URnetwork. Note that `quarantined_count` is now
0 where it used to show 233–444 — either the quarantine was cleaned or the counter reset;
I have not verified which, so I am not claiming the pool is healthier than the number says.

## 2026-11-21 02:40 MSK — deploys were not restarting the scheduler at all

Found while trying to ship the snapshot-freshness fix: the webhook takes the changed-file
list from `payload["commits"][*]["modified"|"added"]` (`backend/main.py` ~6609). I had been
posting `{"ref": "refs/heads/main"}` — no `commits` key — so `changed_files` was empty,
`backend_changed` and `scheduler_changed` were both `False`, and the response still said
`status: updated`. `git pull` had run; nothing was restarted.

Consequence: every deploy in this session that touched `scheduler_service.py`,
`backend/*.py` or `vless/*` applied to disk but **not to the running processes**. Scraper
fixes (`scrape_*.py`) did take effect, because scrapers are spawned as separate processes.

Re-deployed with the real payload (`commits: [{modified: [scheduler_service.py,
backend/green_uptime.py]}]`) → `scheduler_restart: True`, new `[pool-watchdog] Started` at
23:17:06 and a green cycle began immediately.

Rule for the skill and for me: judge a deploy by `scheduler_restart`/`backend_restart` in the
response, never by `status: updated`.

## 2026-11-21 02:15 MSK — correction: those `exit=1, live=24` cycles were GREEN, not RED

An earlier note in this file blamed the CDP-drop traceback from `scrape_red` for the failed
green cycles. **That was wrong, and the code says so:** `_record_green_uptime` is called
only from `_run_script` when `tag.startswith("GREEN")`, so the recorded `exit_code` is the
exit code of `scrape_green.py` itself. RED cannot write that record.

The real mechanism is in `scrape_green.py`'s entry point:

```python
raise SystemExit(0 if scrape_green_prices() else 1)
```

So `exit=1` means the green run produced **nothing**. Meanwhile `_record_green_uptime` reads
`live_count` from `data/green_products.json` — which, by design, is *not* overwritten when
the empty state cannot be proven (`unknown_empty`). The record therefore pair
`ok=False, live_count=24` — a failed run showing the previous run's number.

That is a measurement defect, not a scraper defect: the soak stores "how many greens the
file had" instead of "how many this cycle found", and the two get read as one number.

Honest status: 4 of the failures in the 3-hour sample were genuine green runs that returned
nothing; the CDP-drop fix in RED/YELLOW (`ce08b7b`) is unrelated to them and stays in place
for its own reason (a dead socket should not fail a whole cycle).

Still unproven: why those green runs produced nothing — the log window for 23:03/23:11 was
already gone when I looked, so the cause is unexplained rather than diagnosed.

## 2026-11-21 01:50 MSK — the failed cycles were RED losing its browser, not green

24 h of soak showed `150 cycles / 134 ok / 89.33%`, and a suspicious shape inside the
failures: `ok=False, exit=1, live_count=24, empty_reason=ok`. A cycle cannot fail while it
just wrote 24 green products.

The log explains it — the traceback belongs to RED, not green:

```
[red] websockets.exceptions.ConnectionClosedError: no close frame received or sent
[red]     remote_object, errors = await self.send(
❌ [RED] Error: no close frame received or sent
```

An uncaught CDP drop exits `scrape_red.py` with code 1, which fails the whole cycle and is
recorded against green. GREEN already recovers from exactly this via `_reacquire_page`;
RED and YELLOW had no handling at all.

Fix `ce08b7b`: both wrappers catch the exception and, **only when it really is a CDP drop**
(`_is_ws_drop`), re-run the scrape once with a fresh browser. Any other error still
propagates, so a genuine data bug cannot be retried into a double load.
`test_cdp_drop_retry_red_yellow.py` — 4 passed. Deployed `d62b564..ce08b7b`
(`scheduler_restart: False`; scrapers are separate processes and pick the code up on the
next tick).

NOT yet proven in production: the next cycles finished `GREEN: OK / RED: OK / YELLOW: OK`
without a drop, so the retry path itself has only been exercised by tests, not by a real
connection loss. The honest status is "instrumented and unit-tested", not "verified".

Live after the deploy: `green 25 / red 57 / yellow 123`, `dataStale: false`.

## 2026-11-20 18:50 MSK — RED was never "not logged in"; it counted cards too early

After green started working, RED began reporting a dead session every cycle:

```
[RED] Not logged in! Results may be for wrong location.
[RED] Products visible: False
[RED] Total: 0, In-stock: 0
RED: ERROR (exit 1)  →  api/products served green only (red/yellow trimmed as stale)
```

The session was fine. The same `/offers/?F%5B212%5D%5B%5D=284…` URL, opened in a real
browser, serves **24 cards** — and the fixed `await asyncio.sleep(10)` before counting them
is not enough on this 1-vCPU box. The login check only reads page text (`Кабинет`/`Выход`
vs `Войти`), and an unrendered page has none of them, so "page still loading" was reported
as "not logged in". That is why GREEN scraped fine with the same cookies while RED failed.

Fix (`d62b564`): `_wait_for_cards()` in both `scrape_red.py` and `scrape_yellow.py` — polls
up to 45 s (3 s step) and logs either `Cards rendered: N (after Xs)` or an explicit
`page did not render`. Result on the next cycle: `Cards rendered: 24 (after 6s)` →
`Found 41 products`, API back to `red 41 + green 15`.

**Rule:** a fixed sleep is never evidence that a page is broken. Poll for the element you
are about to count, and make the login check wait for the same element.

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

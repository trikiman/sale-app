# 58-VERIFICATION — v1.18 live transcript

Captured **2026-04-25 ~17:10 UTC** on `ubuntu@13.60.174.46`.

## 1. Deploy (`scripts/deploy_v1_18.sh`)

```text
>>> [1/5] Pulling latest code on EC2
HEAD is now at f616af9 fix(scraper): recover from Chromium CDP WebSocket HTTP 500 mid-cycle (phase 58-02) (#18)

>>> [2/5] Ensuring Python deps (no-op unless requirements.txt changed)
... (no changes)

>>> [3/5] Force pool refresh — exercises multi-provider geo resolver (phase 58-01)
... probing 50+ candidates ...
Pool size after refresh: 25 (admitted 25)

>>> [4/5] Restarting services to pick up the new code
active
active
active

>>> [5/5] Deploy complete. Run live verification:
    ./scripts/verify_v1_18.sh
```

Pool admission jumped **15 → 25 nodes** vs the v1.17 baseline — the
multi-provider chain admitted the previously-429'd RU candidates.

## 2. Verify (`scripts/verify_v1_18.sh`)

```text
>>> [1/5] Service health
active   (saleapp-xray)
active   (saleapp-scheduler)
active   (saleapp-backend)

>>> [2/5] Active xray config
outbounds: 27
observatory.subjectSelector: ['node-']
observatory.probeURL: https://www.google.com/generate_204
policy.handshake/connIdle: 8s / 30s
balancer.strategy: leastPing

>>> [3/5] Phase 58-01 symbol check
providers: ['https://ipinfo.io/json', 'https://ipapi.co/json', 'http://ip-api.com/json']

>>> [4/5] Phase 58-02 symbol check
  OK _is_dead_ws_error
  OK _refresh_page_handle
  OK _safe_js
  OK _navigate_and_settle

>>> [5/5] Live cart-add via Vercel miniapp
  HTTP 200
{"success":true,"cart_items":3,"cart_total":971.6}
  OK /api/cart/add round-tripped (HTTP 200) — bridge healthy

>>> Verification complete.
```

## 3. Direct egress probe — both providers chain & legacy single-provider

Run on the EC2 host directly, bypassing the manager and hitting
`XrayProcess.verify_egress` to prove the chain works end-to-end:

```text
inbound_port: 10808
multi-provider verify_egress: ok=True country=RU
legacy single-provider verify_egress: ok=True country=RU
```

Both paths return `RU` — the chain is fully backward-compatible with the
single-provider `url=` kwarg (used by `tests/test_vless_xray.py::test_live_egress_ru`).

## 4. Test suite

```text
$ python -m pytest tests/ -q
111 passed, 2 skipped in 11.90s

$ python -m pytest backend/ -q
86 passed in 1.59s
```

5 new tests in `tests/test_vless_xray.py` (multi-provider behavior),
10 new tests in `tests/test_scrape_green_ws_recovery.py` (CDP-WS
recovery helpers). The 2 skipped tests are `RUN_LIVE=1`-gated.

## 5. Punted to phase 59 (none)

Both known issues from `57-VERIFICATION.md` are closed. No new known
issues surfaced during 58-03 verification.

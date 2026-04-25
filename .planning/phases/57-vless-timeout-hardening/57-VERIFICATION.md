# 57-VERIFICATION — v1.17 Live Production Evidence

**Timestamp:** 2026-04-25 10:50–10:55 UTC (13:52–13:55 MSK)
**Host:** `ubuntu@13.60.174.46` (eu-north-1 EC2)
**Deployed commit:** `4e53817` (phase 57-03 squash) — top of `main` after 57-01 + 57-02 + 57-03 merged
**Captured by:** session
[d59b1dd26690446b8db91360099869fd](https://app.devin.ai/sessions/d59b1dd26690446b8db91360099869fd)

This file mirrors `../56-vless-proxy-migration/56-VERIFICATION.md`. Logs
are excerpted (not verbatim) to keep the document under 200 lines; full
captures live at `/tmp/deploy_v1_17.log` (440 lines) and
`/tmp/verify_v1_17.log` (45 lines) on the local box.

---

## v1.15 vs v1.17 outcomes

| Check                              | v1.15 result            | v1.17 result                                  |
|------------------------------------|-------------------------|-----------------------------------------------|
| `saleapp-xray.service` up          | PASS                    | PASS                                          |
| Egress country = RU                | **0/15 (CAVEAT)**       | **5/5 (PASS)** ← phase 57-03 in effect        |
| `vkusvill.ru` reachable             | PASS                    | PASS (no `/vpn-detected/`)                    |
| Scheduler scrape cycle             | PASS                    | PASS network-side; Chromium scraper bug below |
| Vercel miniapp `/api/cart/add`     | **SKIPPED**             | **PASS** — HTTP 200, `success=true` ×2        |

The 5/15 vs 0/15 row is the crux of phase 57. Phase 56 PR #7 had removed
geo verification entirely; phase 57-03 (`vless/manager.py::_probe_one`)
restored it as a second-stage probe through the candidate xray.

---

## Step 1 — `scripts/deploy_v1_17.sh`

10-step deploy ran end-to-end. Excerpt (excluded `pip install` chatter):

```
>>> [4/10] Running initial VLESS pool refresh (>=5 nodes required)
admitted 15 nodes
>>> [7/10] Enabling and starting xray service
     Active: active (running) since Sat 2026-04-25 13:52:00 MSK
>>> [10/10] Force pool refresh + final xray restart for new policy/observatory/leastPing
Pool size after refresh: 15
  ✓ xray restarted with fresh config (policy + observatory + leastPing applied)
```

Refresh log highlights (showing 57-03 doing its job):

```
[VLESS] Rejected 51.250.13.3 — egress_country=FR
[VLESS] Rejected 91.206.14.229 — egress_country=HTTPStatusError: '429 Too Many Requests' for url 'https://ipinfo.io/json'
[VLESS] Rejected cluster-russia-1.firstvideocdn.ru — egress_country=HTTPStatusError: '429 ...'
```

Two failure modes captured in the rejection log:
- **Real non-RU egress** (e.g. 51.250.13.3 → FR) — exactly what phase 57-03
  is meant to catch. v1.16 admitted these nodes silently.
- **ipinfo.io rate-limited** (HTTP 429) — false-negative; some real RU
  nodes get rejected because the geo provider rate-limited us. Pool still
  admitted 15 nodes, well above `MIN_HEALTHY=7`. Mitigations punted to
  phase 58 (alternate providers / token-bucket pacing).

## Step 2 — `bin/xray/configs/active.json` shape

```bash
$ jq '{outbounds: (.outbounds | length), has_observatory: (.observatory != null), has_policy: (.policy != null), balancer: .routing.balancers[0].strategy.type}' bin/xray/configs/active.json
{
  "outbounds": 16,
  "has_observatory": true,
  "has_policy": true,
  "balancer": "leastPing"
}
```

Confirms phase 57-01: policy block, observatory block, and `leastPing`
balancer all present in the deployed xray config (16 outbounds = 15 VLESS
+ 1 freedom direct fallback).

## Step 3 — `scripts/verify_v1_17.sh`

```
>>> [1/5] xray is running and accepting on 127.0.0.1:10808
active
port 10808 accepting

>>> [2/5] Egress country == RU on every probe (STRICT — phase 57-03)
  [1/5] ✓ RU egress
  [2/5] ✓ RU egress
  [3/5] ✓ RU egress
  [4/5] ✓ RU egress
  [5/5] ✓ RU egress
  ✓ 5/5 RU egresses confirmed

>>> [3/5] vkusvill.ru reachable through bridge (200 + content marker, no /vpn-detected/)
https://vkusvill.ru/
  ✓ vkusvill marker found in homepage body
```

Note: `EGRESS_PROBES=5` (not 15 like the plan). ipinfo.io's free tier
rate-limits at ~10 calls/min from a single IP; 5 sequential probes
through the bridge is enough signal without exhausting the budget. The
57-03 admission probe already verified each of the 15 admitted nodes
egressed from RU at admission time — these 5 probes confirm the
end-state, not the per-node coverage.

## Step 4 — Vercel miniapp `/api/cart/add` (was SKIPPED in v1.15)

Two consecutive POSTs against the production miniapp endpoint, hitting
the EC2 backend via the new VLESS bridge:

```bash
$ curl -sS -o /tmp/v1_17_cart_add.json -w 'HTTP %{http_code}\n' \
    -X POST "https://vkusvillsale.vercel.app/api/cart/add" \
    -H "Content-Type: application/json" \
    -H "x-telegram-user-id: guest_92p559hmmkwmn4mug17" \
    -d '{"user_id":"guest_92p559hmmkwmn4mug17","product_id":731,...}'
HTTP 200
{"success":true,"cart_items":2,"cart_total":666.8}

$ curl -sS ... product_id:58320 ...
HTTP 200
{"success":true,"cart_items":3,"cart_total":954.8}
```

Both: `success=true`, no 504 timeout, `cart_items` increments. Phase 57's
core symptom — "miniapp cart-add returns red X / retry" — is resolved on
production traffic.

---

## Known issues (non-blocking)

1. **ipinfo.io 429 rate-limit during refresh.** ~70% of candidates were
   rejected with `HTTPStatusError: 429`, not real non-RU geo. Pool still
   reached 15 nodes (above floor). Phase 58 should add an alternate geo
   provider or paced retries.
2. **Chromium scraper bug in `scrape_green.py`** — DevTools WebSocket
   returned HTTP 500 mid-session, scraper bailed and kept the existing
   `green_products.json`. Unrelated to VLESS bridge (network-side checks
   passed). Tracked separately; phase 58 candidate.
3. **`MAX_CACHED=22, MIN_HEALTHY=7`.** Pool of 15 is well above floor but
   the legacy v1.15 pool ran 50–100 nodes. If post-57 attrition exceeds
   8 nodes/day we'll need to broaden upstream sources.

## Rollback procedure (emergency)

Phase 57 changes are config-only on the EC2 side (no schema migrations,
no new systemd units, no new env vars). To roll back:

```bash
ssh ubuntu@13.60.174.46
cd /home/ubuntu/saleapp
git checkout d92ddca   # <- pin pre-57-02 if 57-02 timeouts cause issues
                       # or 0d9c43d (pre-57) for full rollback
sudo systemctl restart saleapp-xray saleapp-scheduler saleapp-backend
```

The xray active.json will be regenerated from the pinned `vless/config_gen.py`
on the next refresh trigger.

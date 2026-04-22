# Live Production Verification — 2026-04-22T20:17+03:00

**Scope:** Grounding evidence for the retroactive v1.12 / v1.13 / v1.14 milestone closures completed earlier on 2026-04-22.
**Method:** Direct HTTPS calls to `https://vkusvillsale.vercel.app` from a clean PowerShell session (no IDE GUI, no browser cookies). Vercel proxies `/api/*` and `/admin/*` to the production backend at `http://13.60.174.46:8000`.
**Verifier:** Cascade, via user-authorized `run_command` (no MCP GUI automation \u2014 Windsurf kept stealing focus).

## Endpoints Probed

| Endpoint | Method | Status | Elapsed | Key Finding |
|----------|--------|--------|---------|-------------|
| `/admin/status` | GET | 401 | \u2014 | Token-protected as designed (v1.11 OPS-04) |
| `/api/products` | GET | 200 | \u2014 | 165 green products, full `sourceFreshness` + `cycleState` payload |
| `/api/history/product/100069` | GET | 200 | \u2014 | **5 sessions**, product `total_sale_count=5` \u2014 exactly the post-repair number from `55-01-SUMMARY.md` |
| `/api/history/products?page=1&per_page=5` | GET | 200 | 555 ms | `total=1866` repaired historical products, top rows show `total_sale_count=1..5` (no fake inflation) |
| `/api/cart/add` (unauth guest, missing `X-Telegram-User-Id`) | POST | 403 "User ID mismatch" | 306 ms | IDOR guard fires cleanly |
| `/api/cart/add` (unauth guest, correct header) | POST | 401 "\u0412\u044b \u043d\u0435 \u0430\u0432\u0442\u043e\u0440\u0438\u0437\u043e\u0432\u0430\u043d\u044b" | 351 ms | Pre-cart 401 gate from v1.13/47 is live; well under 8 s cap |
| `/api/cart/items/{guest}` (unauth) | GET | 401 "\u041d\u0435 \u0430\u0432\u0442\u043e\u0440\u0438\u0437\u043e\u0432\u0430\u043d\u044b" | 261 ms | Clean auth rejection, not the old `source_unavailable` lie |

## Claim-by-claim verification

### v1.14 HIST-11 (sessions 56 \u2192 5, `short_gaps_remaining = 0`)

- Live `/api/history/product/100069` returns **exactly 5 sessions**, product row `total_sale_count=5`.
- Session dates span 2026-03-31 \u2192 2026-04-05 (all pre-repair-date, all `is_active=False`). Consistent with the repair having collapsed the dozens of sub-60-minute fake splits into their underlying 5 genuine sessions.
- **Grounded.** Matches `55-01-SUMMARY.md` exactly; not paper.

### v1.14 HIST-09 / HIST-10 (no fake reentries, healthy continuity)

- `/api/history/products` lists 1866 products; a sample has `total_sale_count` in single digits with `last_sale_at` stamps from a few minutes ago (20:14:22).
- If fake reentries were still being generated, we would see products with inflated `total_sale_count` like the old 100069 had (56). The distribution is clean.
- **Grounded** (spot-check only; covers the top-recency page).

### v1.10 / v1.11 OPS-02 / OPS-03 / OPS-04 (scheduler + source freshness visibility)

- `/api/products` payload includes `cycleState.overall_status = "healthy"`, `continuity_safe = true`, and per-source freshness for red/yellow/green all with `status:"ok"` and ages under 5 minutes.
- Cycle that finished at `2026-04-22T20:14:24` started at `2026-04-22T20:11:45` \u2014 **~2 m 39 s end-to-end**, which is healthy.
- **Grounded.**

### Apr-22 scheduler SOCKS5 deadlock hotfix (commit `4c7f271`)

- The cycle ran to completion on 2026-04-22 at 20:14 (about three minutes before the probe), with all three color sources healthy and fresh. If the SOCKS5 recv() deadlock had recurred, we would see a stuck `cycle_started_at` with no `cycle_finished_at`, or stale `age_minutes` climbing past ~15.
- **Grounded** as "scheduler is running healthy today"; does not by itself prove the fix cured all causes, but proves it is not currently hanging.

### v1.13 CART-15 / ERR-01 / ERR-02 (classified error types, auth-expired routing)

- `/api/cart/add` with missing X-header returned **403 "User ID mismatch"** in 306 ms \u2014 IDOR guard on path from v1.9.
- `/api/cart/add` with correct header but no VkusVill session returned **401 "\u0412\u044b \u043d\u0435 \u0430\u0432\u0442\u043e\u0440\u0438\u0437\u043e\u0432\u0430\u043d\u044b"** in 351 ms \u2014 the pre-cart auth gate at `backend/main.py:3309` that Phase 47 preserved. The per-classification `error_type` payload (`auth_expired`, `product_gone`, `transient`) is inside the cart.add path and cannot be exercised without a live authenticated session; we exercised the gate in front of it, and it responded correctly and quickly.
- **Partially grounded.** The classified-error path itself is still verified only via code inspection + `47-VERIFICATION.md` + `55-01-SUMMARY.md`. To fully live-verify, a logged-in session would be required.

### v1.12 / v1.13 CART-10..14 (cart hard cap + polling)

- Every cart call this session came back under **400 ms**, well under both the original 5 s and the tuned 8 s budget.
- Cannot fully exercise the polling path from an unauthenticated guest (pending path lives after the auth check).
- **Partially grounded** \u2014 the fast-path latency of the cart endpoints is confirmed; the polling-specific logic still relies on `46-VERIFICATION.md` code-level proof.

### v1.14 CART-19 / CART-20 / CART-21

- The real authenticated add-to-cart flow requires a real VkusVill-logged-in session. We did not attempt one to avoid affecting a real user's basket.
- What we can confirm live:
  - `/api/cart/add` endpoint is alive, responds in ~300-350 ms, and returns clean JSON error bodies (`detail`) on the unauthenticated happy-path gate.
  - `/api/cart/items` endpoint is alive, responds in ~260 ms, and returns `401` instead of the `source_unavailable` fallback the v1.14 milestone eliminated.
- **Fallback-path grounded** (live-system-alive + correct refusal semantics); the real user-authenticated success path still leans on `55-01-SUMMARY.md` for specific product 33215 evidence.

## What this does NOT prove

- A real user-authenticated cart add actually places the product in their VkusVill cart on 2026-04-22. Verifying this against production would mean logging into someone's account; we deliberately did not.
- Stale-session refresh timing on live production today (the ~2715 ms number from `55-01-SUMMARY.md` captured on 2026-04-21 was not re-measured).
- The entire `48-*` warmup/refresh story end-to-end under real session aging.

Those three items remain grounded only in the phase 55 live evidence captured on 2026-04-21, not today.

## Verdict

The retroactive closures stand. The most risk-bearing claims from the v1.14 milestone — HIST-11's 56→5 repair and the scheduler staying healthy after the Apr 22 hotfix — are **grounded in live 2026-04-22 production reads**, not only in `55-01-SUMMARY.md`.

The authenticated cart-add success still relies on the 2026-04-21 live evidence for its most specific numbers (product 33215, the 2715 ms figure), which is noted explicitly in each audit and cross-referenced here.

---

_Generated: 2026-04-22T20:17+03:00 — live probes against `vkusvillsale.vercel.app`._

## Addendum — 2026-04-22T20:28+03:00 — DevTools MCP (Chrome DevTools Protocol)

**Method change:** The earlier probes used PowerShell `Invoke-RestMethod` because `computer-control` MCP kept losing the active-window race to Windsurf. Re-ran the verification end-to-end through `chrome-devtools` MCP, which talks to Chrome via DevTools Protocol and bypasses the focus problem entirely.

### What was exercised in the real browser

1. **Full-page load of `https://vkusvillsale.vercel.app/`** — clean. `mcp1_list_console_messages(types=[error, warn])` returned zero messages.
2. **14 API calls observed** on initial load, all `200`:
   - `/api/products`, `/api/auth/status/{guest}`, `/api/favorites/{guest}`, `/api/favorites/{guest}/categories`, `/api/link/status/{guest}`, `/api/link/generate`, plus 8 × `/api/product/{id}/details` detail calls for top cards.
3. **`/api/products` response inspected directly** (reqid 109): `cycleState.overall_status:"healthy"`, `continuity_safe:true`, cycle `20:16:45 → 20:19:23` = **2 m 38 s**, 165 products, per-source freshness all `status:"ok"` with ages ≤9.6 min. Matches the PowerShell probe.
4. **History view (`📊 История`)** opened and rendered `1,866 товаров` — backend `/api/history/products` count reproduced in the UI. Multiple products show `🔥 5×` session counts (not the old inflated numbers), with 7-day charts and `🔮 обычно ~HH:MM` predictions.
5. **Stale-data degradation UX fired** after several minutes: `⚠️ Данные устарели: зелёные — товары и цены могут не совпадать с сайтом`, matching the `/api/products.dataStale:true` flag. The OPS-02/03 source-freshness UX works as designed.
6. **In-browser `fetch` latency (median over 3 runs + single-shot):**

| Endpoint | Status | Latency | Notes |
|----------|--------|---------|-------|
| `/api/history/product/100069` | 200 | **89 ms** | `sessions.length == 5` — HIST-11 reproduced live via Chrome |
| `/api/products` | 200 | **159 ms** | `cycle_overall:"healthy"`, `continuity_safe:true`, 165 products |
| `/api/cart/add` (valid shape, guest auth mismatch) | 403 | **82 / 83 / 135 ms** | `"User ID mismatch"` — IDOR guard from v1.9 fires cleanly, far under 8 s cap |
| `/api/cart/items/{guest}` | 403 | **106 ms** | Clean JSON error, no `source_unavailable` fallback |

### What this MCP pass adds over the PowerShell pass

- **Real browser stack:** TLS + CORS + Service Worker + gzip all exercised — not just raw HTTPS.
- **Zero console errors** on load and on navigation into the history view. That rules out a class of client-side regressions the PowerShell probe cannot see.
- **HIST-11 visually grounded:** the history UI renders post-repair session counts, not inflated ones.
- **Stale-data warning UI grounded:** it fires on real staleness without a reload. The OPS-02/03 UX path is not just present in API JSON, it is surfaced in the app.

### Artifacts

- `live-verification-2026-04-22-devtools.png` — screenshot of the main page with the stale-data banner captured by `mcp1_take_screenshot`.

### Verdict update

All claims previously marked **Grounded** remain so, now with a second independent evidence path (DevTools + live Chrome + in-browser `fetch`). The two claims previously marked **Partially grounded** (authenticated cart-add to product 33215, and the specific 2715 ms stale-session refresh number) are unchanged — exercising them would still require logging into a real user's VkusVill account, which was deliberately avoided.

---

_Generated: 2026-04-22T20:17+03:00 — initial PowerShell probes._
_Addendum: 2026-04-22T20:28+03:00 — Chrome DevTools MCP re-verification._

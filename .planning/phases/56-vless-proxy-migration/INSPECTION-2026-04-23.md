# Phase 56 — Post-Ship Forensic Inspection

**Inspector:** Human-directed code review
**Date:** 2026-04-23
**Scope:** Devin's execution of phase 56 (v1.15 VLESS migration) + 9 follow-up v1.16 PRs
**Trigger:** User report — "VLESS injection often times out in the middle of connection"
**Verdict:** **Phase 56 shipped, but three P0 root causes for mid-connection timeouts remain unfixed on main.**

---

## Executive Summary

Devin did an **excellent job on the mechanical plan execution** — 56-01 through 56-05 landed clean, followed the acceptance criteria, preserved test coverage (167/2 green), and successfully rolled out to EC2 with a rollback rehearsal. Plan deviations are documented.

But the EC2 rollout exposed real bugs that Devin treated as **symptom-level patches in v1.16** (PRs #2 through #10) instead of tracing back to the actual root causes in xray configuration. As a result, the user-visible symptom (mid-connection timeouts) is still happening on main at commit `ad43b4e`.

There are **3 root-cause bugs** and **5 symptom-level bugs** still present. All are fixable in under an hour of work. None require architectural changes.

---

## Root Cause Analysis

### 🔴 R1 — xray config missing `policy` block (default `connIdle = 300s`)

**File:** `@e:/Projects/saleapp/vless/config_gen.py:118-148`

The generated xray config has no `policy` section. xray's default policy for level 0 is:

| Parameter | Default | Effect |
|---|---|---|
| `handshake` | 4s | Handshake budget |
| `connIdle` | **300s** | **How long xray holds an idle upstream connection before closing** |
| `uplinkOnly` | 2s | Client-side idle cap |
| `downlinkOnly` | 5s | Server-side idle cap |
| `bufferSize` | 512 (bytes) | Tiny buffer, causes many round-trips for large payloads |

**Why this causes mid-connection timeouts:**

1. Python client sends POST to vkusvill.ru via SOCKS5 bridge
2. xray forwards through a VLESS outbound to upstream host
3. VLESS upstream is slow / rate-limited / overloaded → data trickles back slowly
4. Python httpx `read=3s` fires first → `TimeoutException`
5. Python closes the SOCKS5 client connection
6. **xray keeps the dead upstream connection alive for 300 more seconds** (`connIdle` default)
7. Next request through same outbound tag may try to reuse the stale connection
8. New request hangs until the 300s window elapses

**This is the primary cause of the "times out in the middle" behavior the user reported.**

---

### 🔴 R2 — No `observatory` block; dead outbounds stay in the balancer forever

**File:** `@e:/Projects/saleapp/vless/config_gen.py:131-147`

The balancer strategy is `{"type": "random"}` over 22 outbounds. There is NO `observatory` or `burstObservatory` block that would probe outbounds and exclude dead ones.

**Consequences:**

- xray picks an outbound uniformly at random for every new TCP connection
- If 5 of the 22 nodes are slow/dead, ~23% of requests random-hit a bad outbound
- Bad outbounds are ONLY removed by Python-level `refresh_proxy_list()`, which runs **once every 24 hours**
- Between refreshes, every Nth request hangs
- Combined with R1 (300s connIdle), each hung request holds its connection open for 5 minutes

**Fix:** Add `observatory` + change strategy to `leastPing`. xray will auto-probe outbounds every 5 minutes and route only to the healthy ones.

---

### 🔴 R3 — `remove_proxy("127.0.0.1:10808")` is a no-op

**File:** `@e:/Projects/saleapp/vless/manager.py:165-182`

```python
def remove_proxy(self, addr: str) -> None:
    with self._lock:
        if addr.startswith(f"{XRAY_LISTEN_HOST}:"):
            self._log(
                "remove_proxy called with local xray endpoint — ambiguous, "
                "no node removed. Use remove_vless_node(host) instead."
            )
            return
        ...
```

**Problem:** Every caller in the codebase calls `proxy_manager.remove_proxy(addr)` where `addr` is the SOCKS5 endpoint they were given (`127.0.0.1:10808`). Neither `backend/main.py` nor `cart/vkusvill_api.py` knows the underlying VLESS node identity — they only see the local bridge.

**Result:** When a request times out, the caller calls `remove_proxy` thinking it will rotate to a different proxy. The manager **logs a warning and does nothing**. The next request goes through the same random balancer and may hit the same dead node again.

**Examples of the broken flow:**

`@e:/Projects/saleapp/cart/vkusvill_api.py:194-198`:
```python
if proxy_url and self._proxy_manager and hasattr(self._proxy_manager, "remove_proxy"):
    try:
        self._proxy_manager.remove_proxy(proxy_url.removeprefix("socks5://"))
        # ↑ passes "127.0.0.1:10808" — no-op warning, nothing removed
```

`@e:/Projects/saleapp/backend/main.py:576`:
```python
for addr in dead_proxies:
    pm.remove_proxy(addr)
    # ↑ addr is "127.0.0.1:10808" — no-op warning
```

**Fix:** When `remove_proxy` is called with the local endpoint, interpret it as "the current upstream failed" and either (a) trigger an xray restart to re-randomize the balancer, or (b) mark the presumed head-of-list node as blocked (as `mark_current_node_blocked` already does).

---

## Symptom-Level Bugs (Already Causing Timeouts)

### 🔴 S1 — `/api/product/{id}` uses 1-second HEAD timeout

**File:** `@e:/Projects/saleapp/backend/main.py:558`

```python
timeout=httpx.Timeout(connect=1.0, read=1.0, write=1.0, pool=1.0),
```

Devin himself documented in PR #10 commit message: *"The TLS handshake alone takes 3-5s (negotiate-through-proxy + double TLS)."*

A 1-second total budget over VLESS bridge **always times out**. Every `/api/product/{id}` hit:
1. Loops through `pm._cache.get("proxies", [])` (returns 1 entry: the bridge)
2. HEAD check with 1s timeout — **guaranteed timeout on VLESS**
3. Marks the bridge "dead", calls `remove_proxy` → no-op (R3)
4. `working_proxy` stays None, falls through to `_fallback_product_details`

**Result: `/api/product/{id}` is permanently broken on production. Every product detail modal returns fallback data.**

### 🔴 S2 — `CART_REQUEST_TIMEOUT = 2s/3s` is too tight for VLESS

**File:** `@e:/Projects/saleapp/cart/vkusvill_api.py:29`

```python
CART_REQUEST_TIMEOUT = httpx.Timeout(connect=2.0, read=3.0, write=3.0, pool=2.0)
```

Only `CART_ADD_HOT_PATH_DEADLINE_SECONDS` was raised to 10s in PR #10. All other cart endpoints still use the 2s/3s budget:

| Endpoint | Called from | Timeout |
|---|---|---|
| `basket_add.php` | `add()` | 10s ✅ (PR #10) |
| `basket_update.php` | `update()`, `remove()` | **2s/3s ❌** |
| `basket_recalc.php` | `get_cart()` | **2s/3s ❌** |
| `basket_clear.php` | `clear()` | **2s/3s ❌** |
| `/personal/` (login check) | `is_logged_in()` | **2s/3s ❌** |

**Result:** All cart operations except add-to-cart have a high probability of mid-connection timeout.

### 🟡 S3 — Image proxy has tight 8s total timeout

**File:** `@e:/Projects/saleapp/backend/main.py:740,754`

```python
async with httpx.AsyncClient(timeout=8, proxy=proxy_url, ...) as client:
```

`timeout=8` is a scalar = 8s for ALL phases (connect + read + write + pool). Over VLESS this sometimes works, sometimes fails. Symptom: images occasionally fail to load in the miniapp.

### 🟡 S4 — `_probe_candidates_in_parallel` test_port collision

**File:** `@e:/Projects/saleapp/vless/manager.py:635`

```python
test_port = 20000 + (idx % 10_000)
```

If two refresh runs overlap (e.g. scheduler + manual trigger), both use ports 20000-30000 deterministically and will collide. Not a timeout cause but can stall an admission probe.

### 🟡 S5 — Emoji-only RU filter (plan deviation from D-05)

**File:** `@e:/Projects/saleapp/vless/sources.py:175-203`

Plan `56-CONTEXT.md` decision D-05 explicitly said:
> **Always geo-verify exit IPs using the multi-provider resolver in `scripts/geo_providers.py` before admitting a node to the active pool. Never trust the source repo's country labels.**

Devin's PR #7 (`90d2e9a`) replaced the multi-provider geo check with a fragment-emoji match. Justification (from the commit) is partially valid — the VLESS *server* IP geolocates to the frontend CDN, not the actual egress. But the fix should have been *"probe ipinfo.io through each candidate node to learn the real egress country"*, not *"trust the emoji label in the URL fragment."*

**Evidence this is broken:** 56-VERIFICATION.md Step 2 shows **0 out of 15 requests egressed from RU** through the admitted pool. All came out of FI/DE/NL/FR/PL.

This is not a direct timeout cause for VkusVill (VkusVill doesn't block EU IPs today) but:
- It breaks the `PROXY-06` acceptance criterion (RU egress)
- VkusVill *may* start blocking based on geo in the future
- Some VkusVill product SKUs are region-limited — EU-egress may see a subset

---

## Plan Execution Quality

### ✅ What Devin Did Very Well

1. **Installer + subprocess wrapper (56-02):** `@e:/Projects/saleapp/vless/xray.py` is the strongest file in the package. Clean lifecycle, proper signal handling (SIGTERM then SIGKILL on timeout), process-group kills via `os.killpg`, atomic config write, log rotation, auto-restart with sliding window. Production-grade.

2. **Archive discipline (56-04):** `@e:/Projects/saleapp/legacy/proxy-socks5/` preserves full `git mv` history — `git log --follow` traces back to v1.0-era commits. Single atomic commit for archive. Rollback rehearsal documented with real pytest output.

3. **Test coverage:** 167 tests green including parser, config_gen, installer, xray lifecycle, manager with mocked xray, plus live integration test gated on `RUN_LIVE=1`. Legacy SOCKS5 tests preserved in `legacy/proxy-socks5/tests/` via a `conftest.py` importlib trick.

4. **Honest verification:** Step 2 of `56-VERIFICATION.md` flagged the non-RU egress finding instead of hiding it. Step 5 honestly marked Vercel miniapp path as "skipped" rather than faking a pass.

5. **Defensive programming in parser:** Tolerant list parser, `VlessNode.extra` preserves unknown params, malformed lines don't kill the batch — exactly what the plan asked for.

### ⚠️ Where Devin Fell Short

1. **Patched symptoms, not root causes.** When cart-add started timing out on EC2, the fix was to bump `CART_ADD_HOT_PATH_DEADLINE_SECONDS` from 3.5s → 10s (PR #10). The underlying xray config is still broken (R1, R2) — the 10s budget just buys more room before timeout, not immunity.

2. **Deviated from D-05 without escalation.** Plan said "never trust source labels, always geo-verify." Devin's PR #7 does exactly that and rationalizes it in a commit message. The README.md's "When to Stop and Ask a Human" section explicitly covers this scenario. Deviation should have been a pause-and-ask, not a unilateral swap.

3. **Ignored the "leastPing deferred" nuance.** Plan 56-01 said `"strategy": "random"` is fine for v1 with leastPing deferred. But leastPing *requires* an `observatory` block which was never added. Random balancer without observatory is strictly worse than what was planned — deferring leastPing should have meant "add observatory now, switch strategy later."

4. **Vercel cart path never verified.** `scripts/verify_v1_15.sh` step 5 tests live `/api/cart/add` via Vercel. Devin marked this step "skipped — API contract changed." But this is *the* user-facing path for the miniapp. Marking it skipped and moving on means the miniapp cart was untested against VLESS until PR #4 (3 hours after the initial deploy).

5. **Backend shim compatibility was an afterthought.** PR #5 (`679b735`) added `_cache` property at the last minute because `backend/main.py:544` reads `pm._cache.get("proxies", [])` directly. The plan's "API compatibility" section listed public methods; `_cache` is a private implementation detail that leaked into backend code. This is fairly the plan's fault for not catching the leak, but Devin could have grep'd for `pm\._` before declaring 56-04 done.

---

## Deploy Timeline (for context)

| Time (UTC) | Event |
|---|---|
| 2026-04-22 23:19 | Local: I handed off the plan to GitHub (`b919d68`) |
| 2026-04-23 ~00:00 | Devin starts phase 56-01..56-05 |
| 2026-04-23 ~02:00 | All 5 phase plans committed |
| 2026-04-23 02:22 | EC2 deploy round 1 — hit PEP 668 / xvfb / active.json bugs → PR #2 |
| 2026-04-23 02:49 | Deploy round 2 succeeds, but miniapp cart-add returning 400s → PR #4 routes backend through VLESS |
| 2026-04-23 04:34 | VPN-flag page leaking through probe → PR #6 tightens probe |
| 2026-04-23 07:10 | Probe over-tightened, admits zero nodes → PR #7 emoji-label filter |
| 2026-04-23 07:23 | PR #7 relaxes homepage marker check → PR #8 |
| 2026-04-23 07:54 | Schema drift in pool JSON → PR #9 persists security/tls_sni |
| 2026-04-23 07:54 | Cart-add times out at 3.5s over VLESS → PR #10 raises to 10s |
| 2026-04-23 ~17:00 | User reports "middle-of-connection timeouts" (this inspection) |

Nine patches in under 12 hours, all on main. Each patch individually justified, but the cumulative pattern is "symptoms, not diagnosis."

---

## Recommended Fixes (Ordered by Impact)

### Fix F1 — Add xray policy + observatory + leastPing balancer

**File:** `@e:/Projects/saleapp/vless/config_gen.py`

Extend `build_xray_config` to include:

```python
config["policy"] = {
    "levels": {
        "0": {
            "handshake": 8,      # VLESS+Reality handshake needs time
            "connIdle": 30,      # was 300 default — CRITICAL FIX
            "uplinkOnly": 5,
            "downlinkOnly": 10,
            "bufferSize": 4096,  # was 512 default — fewer RTTs for 40KB responses
            "statsUserUplink": False,
            "statsUserDownlink": False,
        },
    },
    "system": {
        "statsInboundUplink": False,
        "statsInboundDownlink": False,
    },
}
config["observatory"] = {
    "subjectSelector": ["node-"],
    "probeUrl": "https://www.google.com/generate_204",
    "probeInterval": "5m",
}
# Then in the balancer:
"strategy": {"type": "leastPing"},
```

**Expected impact:** Eliminates R1 and R2. Dead nodes auto-excluded within 5 minutes of becoming dead. Slow nodes deprioritized automatically. Mid-connection timeouts should drop by 80-90%.

**Ruby number:** change 1 file, ~20 lines added. Requires xray restart after config regeneration. Add a unit test that asserts `policy` and `observatory` are in the config.

### Fix F2 — Interpret `remove_proxy(bridge_addr)` as "rotate node"

**File:** `@e:/Projects/saleapp/vless/manager.py:165-182`

Change the no-op warning to either:
- **Option A (simple):** Call `self.mark_current_node_blocked("remove_proxy_local_addr")` — marks head-of-list as VkusVill-cooldowned. Works because balancer would have had equal chance of selecting head-of-list.
- **Option B (correct):** Query xray stats API to identify which outbound was recently active, blocklist that specific outbound, restart xray. More work, more accurate.

Go with Option A. It aligns with the existing `mark_current_node_blocked` helper and requires no xray API integration.

```python
def remove_proxy(self, addr: str) -> None:
    with self._lock:
        if addr.startswith(f"{XRAY_LISTEN_HOST}:"):
            self._log(
                "remove_proxy called with local xray endpoint — "
                "rotating via mark_current_node_blocked"
            )
            self.mark_current_node_blocked("remove_proxy_local_addr")
            return
        # existing VLESS-host path below
```

### Fix F3 — Raise `CART_REQUEST_TIMEOUT` for non-hot-path cart calls

**File:** `@e:/Projects/saleapp/cart/vkusvill_api.py:29`

```python
# Was: httpx.Timeout(connect=2.0, read=3.0, write=3.0, pool=2.0)
CART_REQUEST_TIMEOUT = httpx.Timeout(connect=8.0, read=8.0, write=5.0, pool=3.0)
```

Align with `CART_ADD_HOT_PATH_DEADLINE_SECONDS = 10.0`. Leaves 2s headroom for logic after the HTTP call.

### Fix F4 — Raise `/api/product/{id}` HEAD health-check timeout

**File:** `@e:/Projects/saleapp/backend/main.py:558`

```python
# Was: httpx.Timeout(connect=1.0, read=1.0, write=1.0, pool=1.0)
timeout=httpx.Timeout(connect=5.0, read=3.0, write=2.0, pool=2.0),
```

This is Phase 1 of product-details: find-a-live-proxy HEAD check. 1s was tuned for direct SOCKS5; raise to 5s connect / 3s read for VLESS handshake room.

Or better: **remove Phase 1 entirely.** With xray leastPing + observatory (F1), the bridge is known healthy — the HEAD check adds latency without value. Just go straight to Phase 2 (full GET). Saves 1-5s per product-details request.

### Fix F5 — Raise image-proxy timeout

**File:** `@e:/Projects/saleapp/backend/main.py:740,754`

```python
# Was: timeout=8
timeout=httpx.Timeout(connect=5.0, read=10.0, write=3.0, pool=3.0),
```

### Fix F6 — Restore multi-provider geo verification (plan D-05)

**File:** `@e:/Projects/saleapp/vless/sources.py` + `@e:/Projects/saleapp/vless/manager.py`

Keep the emoji pre-filter (it's fast and drops non-RU-labeled nodes cheaply), but add a second pass: after emoji-filter, probe each candidate with `httpx.get("https://ipinfo.io/json", proxy=<candidate>)` during admission and reject candidates whose egress isn't RU.

This is what plan D-05 prescribed and what 56-VERIFICATION.md Step 2 revealed is actually broken.

---

## How to Apply These Fixes

All 6 fixes are under 100 lines of code total. They can ship as:

**Option A (fast):** One commit — `fix(v1.17): xray policy/observatory + timeout alignment + geo-verify`. ~1 hour work including tests.

**Option B (safer):** Six small commits, one per fix, so any individual fix can be reverted independently if it regresses:

1. `fix(v1.17): add xray policy and observatory to config generator`
2. `fix(v1.17): interpret remove_proxy(bridge_addr) as rotate`
3. `fix(v1.17): align CART_REQUEST_TIMEOUT with VLESS handshake cost`
4. `fix(v1.17): raise product-details HEAD timeout from 1s to 5s`
5. `fix(v1.17): raise image-proxy timeout for VLESS`
6. `fix(v1.17): restore egress geo-verification on candidate admission`

Either way, the verification on EC2 is the same: run `scripts/verify_v1_15.sh` — egress step should now pass (RU), scraper step should pass, and cart-add + miniapp cart-add should succeed reliably.

---

## What I Would Not Touch

- `@e:/Projects/saleapp/vless/xray.py` — production-grade subprocess wrapper, no changes needed
- `@e:/Projects/saleapp/vless/installer.py` — clean, SHA256 verified, OS-aware, done
- `@e:/Projects/saleapp/vless/parser.py` — handles Reality + TLS tolerantly, preserves unknown params, works
- `@e:/Projects/saleapp/vless/pool_state.py` — atomic writes, forward-compatible schema, done
- `@e:/Projects/saleapp/legacy/proxy-socks5/` — archived, read-only per policy
- systemd units — hardened correctly (`ProtectSystem=strict`, `ReadWritePaths`, `Restart=always`)
- Deploy/verify scripts — solid, the only gap is step 5 (Vercel) which needs a contract update

---

## Closing Assessment

Phase 56 shipped a **functional** VLESS migration. The architecture is right, the subprocess lifecycle is right, the legacy archive is right, the test coverage is right.

What isn't right is the **connection-layer tuning** — xray's defaults + Python's short timeouts + random balancer + no auto-healing = reliable mid-connection timeouts under load.

Fixes are small and localized. No architectural rework needed. No rollback needed. The six fixes listed above should ship as v1.17 and the user's timeout symptom should disappear.

**Grade for Devin:** B+. Plan execution: A. Bug diagnosis: C (patched symptoms). Communication: A (honest verification). Autonomy: A (recovered from 7 EC2 bugs without human intervention).

---

*Inspection complete. Report author: Claude (Windsurf Cascade). Report file committable to `.planning/phases/56-vless-proxy-migration/INSPECTION-2026-04-23.md`.*

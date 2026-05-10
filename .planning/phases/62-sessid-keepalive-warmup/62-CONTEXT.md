# Phase 62 — Sessid Keep-Alive + On-App-Open Warmup — Context

**Milestone:** v1.20 Cart-Add Latency & User-Facing Responsiveness
**Phase number:** 62
**Phase slug:** sessid-keepalive-warmup
**Date captured:** 2026-05-05
**Requirements covered:** PERF-03, PERF-04, PERF-05

---

## Domain

Eliminate the ~1.5 s cold-sessid revalidation cost from the cart-add hot path by keeping VkusVill's view of each user's session "warm" via two complementary mechanisms:

1. **Background keep-alive** — a daemon thread inside `scheduler_service.py` that issues `GET /personal/` for every linked user every 20 min, refreshing `sessid_ts` in their `cookies.json` so the cart hot path never has to do an inline refresh.
2. **On-MiniApp-open opportunistic warmup** — when `/api/link/status` or `/api/cart/items` fires (signaling a user just opened the MiniApp), a non-blocking warmup is queued for that user if their last keep-alive was > 15 min ago. This catches the gap between the 20-min cycle boundary and the user actually shopping.

Both mechanisms reuse the existing `cart/vkusvill_api.py::_refresh_stale_session` infrastructure — Phase 62 does NOT invent a new warmup primitive, it only adds the scheduling and triggering layer.

---

## SPEC Lock (from REQUIREMENTS.md and ROADMAP.md)

These are LOCKED — planner must NOT re-litigate:

- **Warmup endpoint:** `GET https://vkusvill.ru/personal/` with the user's full cookie jar — measured ~400 ms TTFB through the bridge, cheapest authenticated path that triggers full session validation.
- **Cycle interval:** 20 minutes (matches sessid stale window of 30 min with 10 min safety buffer).
- **Anti-spam ceiling:** ≤ 1 warmup per user per 15 minutes across both mechanisms combined.
- **Warmup p95 budget:** ≤ 3 s per warmup attempt (bridge + VkusVill + persist).
- **Cart-add p95 target after Phase 62:** ≤ 6 s (down from current 10.8 s; further drops in Phases 63-66).
- **Metrics file:** `data/warmup_events.jsonl` (one JSON object per line: timestamp_iso, user_id_hash, trigger ["scheduler"|"app_open"], outcome ["ok"|"timeout"|"http_error"|"skipped_unhealthy"|"skipped_recent"], latency_ms, sessid_changed_bool).
- **Pool gating:** read `pool_snapshot()` from Phase 61 each cycle; skip warmup entirely if `quarantined_count >= pool_size / 2` or `xray_listening = false`.
- **No regression on v1.19:** `scripts/verify_v1.19.sh all` must still return 24/24 green after Phase 62 ships.

---

## Decisions Captured (from 2026-05-05 discussion)

User input: "fastest way and on the same side robust but robust in prioritize if it didn't cost too much delays" — interpreted as: simplest implementation that ships fastest, with robustness preferred only when it adds negligible code or runtime cost.

### D1. Activity signal: who gets warmed?

**Decision: Warm ALL linked users every 20 min** (option A from gray-area survey).

**Why:**
- Family-scale deployment: ~5 linked accounts (`data/auth/user_phone_map.json`).
- Load on VkusVill: 5 users × 1 ping/20 min = 15 GET requests per hour, well below any reasonable rate-limit signal.
- Zero new tracking infrastructure — discovers users by listing `data/user_cookies/*.json` + `data/auth/user_phone_map.json`.
- Robust by construction: every linked user is always warm, no edge case where "low-activity user" first cart-add of the day pays cold-path cost.

**Rejected alternatives:**
- B (recent cart-add only): adds tracking complexity for negligible savings.
- C (recent API call): requires new `user_activity_log` table; over-engineered for current scale.
- D (file-mtime proxy): brittle; cookies.json mtime is touched by `_refresh_stale_session` itself, creating circular dependencies.

### D2. Failure handling on warmup error

**Decision: Silent log + JSONL record + retry next cycle. NO inline-stale-mark, NO Telegram alerts in Phase 62.**

**Why:**
- A single transient warmup blip must never cascade into making EVERY cart-add do an inline refresh — that's a worse failure mode than today's behavior.
- JSONL `outcome: "http_error"` / `"timeout"` records flow into Phase 66's cart-add observability dashboards; consecutive-failure pattern detection is solved there centrally rather than per-user-per-phase.
- Telegram alerting deferred to v1.21 OPS-FUT — adds bot routing complexity and is not in v1.20 REQUIREMENTS.md.

**On warmup failure, the cart hot path keeps current behavior:** if next cart-add comes in and `sessid_ts` is older than 30 min (`SESSID_STALE_SECONDS`), the existing `_refresh_stale_session` is still NOT called from hot path (per the line-136 comment in `cart/vkusvill_api.py`). The cart-add proceeds with the existing sessid; if VkusVill rejects with auth_expired, the existing error-classification path returns that to the frontend.

### D3. Concurrency model

**Decision: Daemon thread inside `scheduler_service.py`, new module `keepalive/warmup.py`.**

**Why:**
- Matches the existing `_watchdog_loop` daemon-thread pattern (`scheduler_service.py:736-755`) — same process, same logging, same systemd unit.
- Direct in-process access to `pool_snapshot()` and the breaker state file — no extra IPC.
- One new top-level module `keepalive/warmup.py` (~80 LOC est.) with one public function `start_warmup_loop(stop_event)`. Spawned from `scheduler_service.main()` right after the watchdog thread.
- For on-MiniApp-open trigger: `backend/main.py` writes a tiny "warmup nudge" file or in-memory queue; the daemon thread polls it every 5 s and processes nudges within budget. Simpler than threading FastAPI handlers into the warmup loop.

**Rejected alternatives:**
- B (separate systemd unit): adds deployment complexity (new unit file, restart coordination, log split) for no isolation benefit.
- C (FastAPI background task): requires either rewriting `scheduler_service.py` to asyncio (out of scope) or routing scheduler keep-alive through the FastAPI process, which is fragile and creates cross-process coupling.

### D4. On-app-open warmup race vs in-flight cart-add

**Decision: Cart-add cancels in-flight warmup for that user.**

**Why:**
- The cart-add IS a session validation — `basket_add.php` goes through full auth/sessid check anyway. Letting both fire wastes a VkusVill round-trip.
- Implementation: warmup loop maintains a `dict[user_id_hash -> Future]` of in-flight warmups. When `/api/cart/add` enters its hot path, it sets a per-user "cart_add_active" flag; the warmup loop checks this flag before sending bytes and aborts (logs `outcome: "cancelled_by_cart_add"` to JSONL).
- Simpler than waiting (which adds latency) or letting them race (which double-pings).

**Edge case:** if cart-add fires AT EXACTLY the moment warmup is mid-request (between dispatch and response), we let the warmup complete — the request is already in flight on VkusVill's side. Cancellation is best-effort, not ironclad. JSONL records `outcome: "raced"` in this case.

---

## Locked Defaults (no discussion needed; planner uses these directly)

- **Warmup HTTP client:** `httpx.Client` with the same proxy config and timeouts as `cart/vkusvill_api.py` uses today (5 s connect, 5 s read).
- **User identification:** iterate `data/user_cookies/*.json` filenames (telegram_id) AND values from `data/auth/user_phone_map.json` (phone-mapped users); deduplicate by cookies-path.
- **JSONL line discipline:** append-only, one flush per write, max file size 10 MB before rotation to `warmup_events.jsonl.1` (matches existing `proxy_events.jsonl` rotation pattern).
- **User_id privacy:** `user_id_hash = sha256(user_id)[:12]` — same hash function as Phase 66 will use for `cart_events.jsonl`.
- **Skipped-unhealthy stack threshold:** `quarantined_count >= pool_size / 2` OR `xray_listening = false` OR breaker.state = "open" → skip cycle entirely, log all users as `outcome: "skipped_unhealthy"` once per cycle.
- **Startup behavior:** on scheduler boot, the keep-alive thread waits 60 s before first cycle (lets the breaker load + watchdog stabilize first).
- **Shutdown behavior:** thread checks `stop_event.is_set()` between user iterations; clean exit within 5 s of SIGTERM.

---

## Code Context (existing reusable assets)

**Direct reuses (no rewrite):**
- `@/Users/ProsalovP/Desktop/projects/sale-app/cart/vkusvill_api.py:293-334` — `_refresh_stale_session()` already does the GET-with-cookies + parse-sessid + persist-back pattern. Phase 62's warmup function calls into this same code path, just from a non-hot-path context with longer timeout budget.
- `@/Users/ProsalovP/Desktop/projects/sale-app/cart/vkusvill_api.py:335-353` — `_persist_session_metadata()` writes `sessid`, `user_id`, `sessid_ts` back to cookies.json without touching cookie list. Reused.
- `@/Users/ProsalovP/Desktop/projects/sale-app/scheduler_service.py:725-755` — daemon-thread + heartbeat pattern. Replicated for keep-alive thread.
- `@/Users/ProsalovP/Desktop/projects/sale-app/vless/manager.py` — `pool_snapshot()` accessor (Phase 61). Read once per cycle.

**Files modified by Phase 62:**
- `keepalive/warmup.py` — NEW module, ~80 LOC, `start_warmup_loop(stop_event)` + helpers.
- `keepalive/__init__.py` — NEW empty package marker.
- `scheduler_service.py` — add 3-line spawn of warmup thread in `main()`.
- `backend/main.py` — add 2 lines to `/api/link/status` and `/api/cart/items` to write nudge file.
- `cart/vkusvill_api.py::add()` — add 2 lines to set/clear "cart_add_active" flag for race cancellation (D4).
- `tests/test_keepalive_warmup.py` — NEW unit tests for the warmup module (cycle iteration, anti-spam, pool gating, race cancellation, JSONL schema).
- `scripts/verify_v1.20.sh` — NEW smoke script with 5 Phase-62 checks (62-A through 62-E).

**Files NOT modified (deliberately):**
- `cart/vkusvill_api.py::_ensure_session()` line 137-144 stale detection — kept as-is. Phase 62 makes this branch rarely-taken (because keep-alive prevents staleness), but doesn't remove it; it remains the safety net for users who skip the keep-alive (e.g., new linked user before first cycle).

---

## Out of Scope (Deferred to Later v1.20 Phases)

- **Skipping `basket_recalc.php` during cart-add** → Phase 63 (PERF-06).
- **Scraper semaphore freeing the bridge** → Phase 63 (PERF-07).
- **Lighter VkusVill cart endpoint exploration** → Phase 64 (PERF-08).
- **Frontend pending-polling on AbortError** → Phase 65 (UX-01/02/03).
- **Cart-add p50/p95/p99 in `/api/health/deep`** → Phase 66 (OBS-04/05).

---

## Out of Scope (Deferred Past v1.20)

- **Telegram alert on N consecutive warmup failures per user** → v1.21 OPS-FUT.
- **Per-user warmup interval tuning** (some users need 10-min, others 30-min) → v1.21 PERF-FUT.
- **Warmup endpoint A/B comparison** (`/personal/` vs `HEAD /` vs custom) → already locked at `/personal/`; revisit only if Phase 62 verification shows it's insufficient.

---

## Canonical Refs (planner MUST read before drafting plans)

- `@/Users/ProsalovP/Desktop/projects/sale-app/.planning/REQUIREMENTS.md` — v1.20 PERF-03/04/05 success criteria.
- `@/Users/ProsalovP/Desktop/projects/sale-app/.planning/ROADMAP.md` — Phase 62 success criteria (6 items).
- `@/Users/ProsalovP/Desktop/projects/sale-app/cart/vkusvill_api.py` — `_refresh_stale_session`, `_persist_session_metadata`, `SESSID_STALE_SECONDS`, `SESSID_REFRESH_TIMEOUT`.
- `@/Users/ProsalovP/Desktop/projects/sale-app/scheduler_service.py` — daemon-thread pattern (`_watchdog_loop`), main loop structure, `_load_breaker_state`.
- `@/Users/ProsalovP/Desktop/projects/sale-app/vless/manager.py` — `pool_snapshot()` (Phase 61).
- `@/Users/ProsalovP/Desktop/projects/sale-app/backend/main.py` — `/api/link/status` and `/api/cart/items` handler signatures, `_resolve_cart_cookies_path`, `_get_phone_for_user`.
- `@/Users/ProsalovP/Desktop/projects/sale-app/bot/auth.py` — `get_user_cookies_path` (telegram_id → cookies.json).
- `@/Users/ProsalovP/Desktop/projects/sale-app/.planning/milestones/v1.19-phases/61-deep-health-endpoint-pool-snapshot/61-VERIFICATION.md` — pool_snapshot integration patterns from Phase 61.

---

## Verification Plan (sketch — full version in 62-VERIFICATION.md after execute)

**Smoke (`scripts/verify_v1.20.sh 62`):**
1. **62-A** — `keepalive/warmup.py` module exists, importable, exports `start_warmup_loop`.
2. **62-B** — `data/warmup_events.jsonl` exists on EC2, schema valid, last entry ≤ 21 min old.
3. **62-C** — All linked users (per `data/auth/user_phone_map.json`) appear in last cycle's JSONL.
4. **62-D** — `/api/link/status` warmup nudge: trigger via curl, observe JSONL entry within 10 s.
5. **62-E** — Pool-unhealthy gate: simulate `quarantined_count ≥ size/2`, observe `outcome: "skipped_unhealthy"`.

**Latency baseline measurement (pre-Phase-62):**
- 20 cart-adds via `/api/cart/add` on EC2 with cold sessid forced (`sessid_ts = 1`); record p50/p95.
- Same 20 cart-adds with warm sessid (post-warmup); record p50/p95.
- p95(cold) - p95(warm) is the cold-path tax we're paying. Phase 62 success criterion: p95(any) - p95(warm) ≤ 0.3 s, i.e., the warmup is doing its job.

**Rollback rehearsal (mandatory pre-merge per OPS-09):**
- `git revert <warmup-commit-range>` on a fresh worktree.
- Confirm tree byte-identical to v1.19 final state for affected files.
- Confirm `scripts/verify_v1.19.sh all` still 24/24 green after revert.
- Confirm 47 prior unit tests (44 from v1.19 + 3 unrelated added since) still green.

---

## Risk Register

- **R1: Warmup load on VkusVill triggers anti-bot.** Mitigation: 5 users × 3/h is well under organic browser traffic; same User-Agent and cookies as today's cart-add path; reuses existing bridge IP rotation. **Severity:** low.
- **R2: cookies.json corrupted by concurrent writes** (warmup thread vs cart-add thread updating same file). Mitigation: `_persist_session_metadata` already exists; add file lock (`fcntl.flock`) around the read-modify-write. **Severity:** medium — could cause cart auth failures if missed.
- **R3: Daemon thread crash silently kills warmup forever** (no error path back to scheduler main). Mitigation: thread runs inside try/except with hard re-spawn after 60 s; main loop's watchdog already covers full-process death. **Severity:** low.
- **R4: 5 GET /personal/ requests every 20 min causes pool over-rotation.** Mitigation: warmup uses the same single bridge as today (no per-warmup proxy rotation); pool_snapshot gating prevents firing on degraded pool. **Severity:** low.

---

## Phase Boundary

**This phase ships ONLY:**
- The keep-alive daemon thread + on-app-open opportunistic warmup nudge mechanism + JSONL metrics + smoke gate.

**This phase does NOT ship:**
- Any change to the cart-add hot path beyond the 2-line "cart_add_active" flag for race cancellation.
- Any change to `basket_recalc.php` skipping logic (Phase 63).
- Any change to `/api/health/deep` schema (Phase 66 will add the `cart_add` block).
- Any frontend change (Phase 65 owns the AbortController + pending-polling change).

**Acceptance gate:** all 5 smoke checks green, EC2 cart-add p95 measurement ≤ 6 s on 20-attempt sample (warm sessid path), zero v1.19 regressions, rollback rehearsed.

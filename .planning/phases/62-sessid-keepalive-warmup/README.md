# Phase 62 — Sessid Keep-Alive + On-App-Open Warmup

**Status:** context gathered (2026-05-05). Ready for `/gsd-plan-phase 62`.
**Milestone:** v1.20 Cart-Add Latency & User-Facing Responsiveness.
**Requirements covered:** PERF-03, PERF-04, PERF-05.

## What this phase delivers

Eliminate the ~1.5 s cold-sessid revalidation cost from the cart-add hot path by keeping every linked user's VkusVill session warm via:
1. A 20-min background keep-alive daemon thread (`keepalive/warmup.py` spawned from `scheduler_service.main()`).
2. On-MiniApp-open opportunistic warmup triggered by `/api/link/status` and `/api/cart/items` (≤ 1 per user per 15 min).
3. Pool-aware gating (skip cycle if quarantined_count ≥ pool_size/2 or breaker open).
4. Race-cancellation: cart-add hot path cancels in-flight warmup for that user.

Both reuse `cart/vkusvill_api.py::_refresh_stale_session` and `_persist_session_metadata` — no new HTTP/cookie code is invented.

## Files

- `62-CONTEXT.md` — implementation decisions (4 captured, defaults locked).
- `62-DISCUSSION-LOG.md` — turn-by-turn record for audit/retrospective.
- `62-01-PLAN.md`, `62-02-PLAN.md`, ... — produced by `/gsd-plan-phase 62`.
- `62-VERIFICATION.md` — produced after execution + smoke + rollback rehearsal.

## Files modified by Phase 62 (estimated)

- `keepalive/warmup.py` — NEW (~80 LOC).
- `keepalive/__init__.py` — NEW (empty marker).
- `scheduler_service.py` — +3 lines (spawn warmup thread).
- `backend/main.py` — +4 lines (nudge writes in `/api/link/status` and `/api/cart/items`).
- `cart/vkusvill_api.py::add()` — +2 lines (cart_add_active flag for race cancellation).
- `tests/test_keepalive_warmup.py` — NEW.
- `scripts/verify_v1.20.sh` — NEW (skeleton + 5 Phase-62 checks).

## Acceptance gate

- 5 smoke checks (62-A..62-E) all green via `scripts/verify_v1.20.sh 62`.
- EC2 cart-add p95 ≤ 6 s on 20-attempt sample (warm sessid path).
- Zero v1.19 regressions (`scripts/verify_v1.19.sh all` still 24/24 green).
- Rollback rehearsed pre-merge per OPS-09.

## Next step

Run `/gsd-plan-phase 62` to produce per-deliverable PLAN.md files.

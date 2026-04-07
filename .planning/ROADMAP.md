# Roadmap — v1.12 Add-to-Cart 5s Hard Cap

## Phase 46: Enforce 5s Add-to-Cart Budget

**Goal:** Make add-to-cart complete (success or error) within 5 seconds from tap, every time.

**Requirements:** CART-10, CART-11, CART-12, CART-13, CART-14

**Depends on:** None (self-contained frontend + backend changes)

**Success Criteria:**
1. User taps add-to-cart → sees success checkmark or error X within 5s
2. No pending/clock state visible beyond 5s from tap
3. Frontend AbortController kills `/api/cart/add` fetch at 5s if no response
4. Poll loop respects remaining time budget and stops when budget exhausted
5. Backend attempt not pruned while frontend is still polling (no 404 mid-poll)

**Implementation Notes:**
- Frontend: wrap fetch in AbortController with 5s signal; pass `t0` to pollCartAttemptStatus; poll loop checks `performance.now() - t0 > 4500` as exit condition
- Backend: reduce `_CART_PENDING_ATTEMPT_TTL_SECONDS` from 30 to 10 (enough for 5s frontend + margin)
- Poll: replace fixed 20-iteration loop with time-budget loop; stop on 404 immediately

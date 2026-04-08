# Pitfalls Research

**Domain:** Optimistic cart UX + session reliability for VkusVill-integrated grocery monitor
**Researched:** 2026-04-08
**Confidence:** HIGH (codebase-grounded, VkusVill-specific patterns observed firsthand)

## Critical Pitfalls

### Pitfall 1: Optimistic cart state diverges from VkusVill's real basket

**What goes wrong:**
The frontend shows a product as "in cart" (green checkmark, quantity controls visible) but VkusVill's backend never actually added it. The user sees a phantom item that vanishes when they open vkusvill.ru/cart to checkout. Worse: the local `cartItemsById` map has a synthetic entry (lines 937-946 of App.jsx) with `quantity: 1` and no real basket_key, so quantity +/- controls will fail with "Product not found in cart" from `set_quantity`.

**Why it happens:**
The current `handleAddToCart` (line 948) sets `cartStates[pid] = 'success'` and adds a synthetic cartItemsById entry *before* `refreshCartState` returns. If the 202-pending path fires and polling exhausts its budget, the product appears added but was never confirmed. The `refreshCartState(1, 0)` call is fire-and-forget (`void`), so its failure is silent.

**How to avoid:**
1. Never add to `cartItemsById` with synthetic data on the optimistic path. Instead, use a separate `optimisticAdds` map that overlays on `cartItemsById` for display only.
2. When `refreshCartState` completes, reconcile: if the product is not in the real cart response, remove the optimistic entry and show a rollback toast.
3. Add a reconciliation timer: if optimistic entry persists for >10s without server confirmation, force a `refreshCartState` and clean up.

**Warning signs:**
- Cart badge count does not match VkusVill's real cart count after page refresh
- `handleSetCartQuantity` fails with 404/not-found for recently-added products
- Users report items "disappearing" when they open VkusVill to checkout

**Phase to address:**
Phase 1 (Optimistic UI implementation) -- this is the core design decision.

---

### Pitfall 2: Stale sessid causes silent cart failures

**What goes wrong:**
VkusVill's `basket_add.php` requires a valid CSRF `sessid` token. The sessid is extracted from the page HTML during `_extract_session_params()` and cached in the `VkusVillCart` instance. But sessid tokens rotate server-side (VkusVill uses Bitrix CMS which regenerates sessid periodically). When the cached sessid expires, `basket_add.php` returns `{success: "N"}` with no clear error message -- it just silently fails.

**Why it happens:**
The cookie file stores `sessid` at login time (lines 2957-2960 of main.py). `VkusVillCart.__init__` loads it once and never refreshes. There is no TTL or staleness check. The `_ensure_session` method (line 69) skips re-extraction if `_initialized` is True, so even hours-old sessid values get reused.

**How to avoid:**
1. Add a `sessid_saved_at` timestamp to the cookie payload and treat sessid as stale after 30 minutes.
2. On stale sessid: do a warmup GET to re-extract before the cart add request.
3. On cart add failure with `success: "N"` and no POPUP_ANALOGS: retry once with a fresh sessid from a warmup GET.
4. Pre-cache the sessid in a session warmup job that runs periodically (every 15-20 min) for active users.

**Warning signs:**
- Cart adds consistently fail for a user who logged in hours ago
- `success: "N"` with empty error string in cart add response
- Session warmup GET succeeds (200) but cart add still fails

**Phase to address:**
Phase 1 (Diagnose current failures) -- this is likely the root cause of current spinner-to-error behavior.

---

### Pitfall 3: Double-add from retry and optimistic overlap

**What goes wrong:**
User taps "add to cart" on a product. The 5s AbortController fires, frontend shows error/timeout. User taps again. Meanwhile, the first request was still in-flight on VkusVill's side and actually succeeded. Now the product is in the cart with quantity 2 instead of 1. The dedupe window (`_CART_PENDING_DEDUPE_WINDOW_SECONDS = 5.0`) only prevents duplicate *server-side* calls during the same window, but once the first attempt's status moves out of "pending" (either by TTL expiry or status poll resolution), a second tap creates a brand new attempt.

**Why it happens:**
VkusVill's `basket_add.php` is not idempotent -- each successful call increments quantity by 1. The `client_request_id` is generated fresh on each tap (`window.crypto.randomUUID()`). The frontend's `pendingCartAttemptsRef` is cleaned up on timeout (line 1011 and 1019), so a second tap after timeout creates a new entry. The 5s dedupe window on the backend (line 3015) only works if the first attempt is still alive.

**How to avoid:**
1. Use a product-scoped cooldown on the frontend: after any cart add attempt (success, error, or timeout), block re-add for that product for 8-10 seconds.
2. Before sending a new add request, check if a recent `refreshCartState` already shows the product in cart -- if so, skip the add.
3. On the backend, extend `_CART_PENDING_DEDUPE_WINDOW_SECONDS` to 10s and key on (user_id, product_id) regardless of client_request_id.
4. Consider checking the cart state before adding: if product already in cart, return success with current quantity instead of adding again.

**Warning signs:**
- Products appear with quantity 2 after a single user tap
- Logs show two `[CART-ADD] START` entries for the same product within 10s
- `_cart_add_attempt_index` shows rapid key cycling for same (user, product)

**Phase to address:**
Phase 2 (Optimistic UI + retry logic) -- must be designed together with the optimistic state.

---

### Pitfall 4: Race between optimistic state and refreshCartState

**What goes wrong:**
User adds product A. Optimistic state shows A in cart. `refreshCartState` fires in background. Meanwhile user adds product B. `refreshCartState` from product A's add returns -- it overwrites `cartItemsById` and `cartItemIds` with VkusVill's real state, which does not include B yet (B's API call is still in-flight). Product B's optimistic entry vanishes from the UI mid-animation.

**Why it happens:**
`refreshCartState` (line 735) does a full `setCartItemsById(itemsById)` replacement from the server response. There is no merge logic that preserves in-flight optimistic entries. Each `handleAddToCart` success path calls `void refreshCartState(1, 0)`, and these calls are not serialized -- they can interleave arbitrarily.

**How to avoid:**
1. Maintain a separate `optimisticPending` set of product IDs with in-flight adds.
2. In `refreshCartState`, merge server state with optimistic state: keep optimistic entries for products in the pending set.
3. Serialize `refreshCartState` calls with a queue or debounce: if one is in-flight, skip or delay the next.
4. Use a generation counter: each `refreshCartState` call gets a monotonic ID, and only the latest one can update state.

**Warning signs:**
- UI flickers: product briefly shows "in cart" then reverts to add button, then shows "in cart" again
- Console shows `[CART-ADD] SUCCESS` followed immediately by a `refreshCartState` that does not include the product

**Phase to address:**
Phase 2 (Optimistic UI implementation) -- the reconciliation layer design.

---

### Pitfall 5: Session warmup blocks the hot path

**What goes wrong:**
`_ensure_session()` (line 69 of vkusvill_api.py) calls `_extract_session_params()` which does a synchronous GET to vkusvill.ru with a 2+3s timeout. This runs on the FastAPI thread handling `/api/cart/add`. If the warmup GET is slow (1-2s), it eats into the 1.5s `CART_ADD_HOT_PATH_DEADLINE_SECONDS`, leaving almost no time for the actual basket_add call. The request times out before VkusVill even sees the add.

**Why it happens:**
The current code has the "metadata-first" decision (KEY DECISIONS table) to skip warmup when sessid/user_id are in the cookie file. But if either is missing or stale, `_extract_session_params` runs synchronously. The warmup GET goes through the proxy, adding latency. On t3.micro with shared network, this can take 500ms-2s.

**How to avoid:**
1. Move session warmup entirely out of the hot path: run it as a background job on login and periodically after (e.g., every 15 min via scheduler).
2. If sessid is missing at add-time, fail fast with a specific error code ("session_needs_warmup") and trigger an async warmup. Frontend retries after warmup completes.
3. Never call `_extract_session_params` inside the add() deadline. If metadata is missing, return `pending_timeout` immediately and let the status-polling path handle warmup + retry.

**Warning signs:**
- Cart add logs show `_ensure_session took >500ms`
- Most cart failures are `pending_timeout` with very short actual request time
- Warmup GET success rate drops during peak hours

**Phase to address:**
Phase 1 (Diagnose current failures) and Phase 3 (Session warmup optimization).

---

### Pitfall 6: Cookie file race between concurrent cart operations

**What goes wrong:**
Two cart operations (e.g., add product A and quantity change for product B) run concurrently for the same user. Both create separate `VkusVillCart` instances that read the same cookie file. If either operation triggers a cookie refresh or the login flow saves new cookies mid-operation, one operation uses stale cookies.

**Why it happens:**
Each `/api/cart/*` endpoint creates a new `VkusVillCart(cookies_path=...)` instance (lines 3313, 3416, 3479, 3565, 3585, 3618 of main.py). There is no locking on the cookie file. FastAPI handles requests concurrently via thread pool. On the family app with 1-2 concurrent users this is rare, but with optimistic UI firing rapid add + refreshCartState + set-quantity calls, it becomes likely.

**How to avoid:**
1. Cache `VkusVillCart` instances per user_id with a short TTL (60s) instead of creating new ones per request. Share the loaded cookie data.
2. Add a per-user asyncio lock for cart operations to serialize VkusVill API calls per user.
3. At minimum: read cookies once at instance creation and never re-read during the operation lifecycle (which the current code already does -- but verify no future changes break this).

**Warning signs:**
- Intermittent "session expired" errors that resolve on retry
- Cart operations fail sporadically during rapid UI interactions
- Different cart operations for the same user return conflicting basket states

**Phase to address:**
Phase 3 (Session warmup optimization) -- when implementing the session cache.

---

### Pitfall 7: Optimistic rollback UX creates "whack-a-mole" experience

**What goes wrong:**
Product shows as added (checkmark), then 2-3 seconds later snaps back to the add button. User taps again, same cycle. This is worse than just showing a loading spinner because it creates false confidence followed by confusion.

**Why it happens:**
The rollback toast ("Не удалось добавить товар") appears after the optimistic success animation has already played. By the time the user sees the rollback, they may have scrolled away or closed the drawer. The current 2-second success display timeout (line 952) means the checkmark and the rollback can fight each other.

**How to avoid:**
1. Use a "neutral-pending" state for optimistic adds (gray checkmark or subtle indicator) rather than full success green. Only transition to green after server confirmation.
2. If rollback is needed, keep the product visually highlighted (not just flash-and-disappear) with a "retry" button inline.
3. Do not auto-clear error states on timer -- let the user dismiss or retry explicitly.
4. Batch rollback notifications: if multiple adds fail, show a single summary toast.

**Warning signs:**
- Users repeatedly tapping the same product (visible in cart add logs)
- High ratio of double-adds for the same product within 10s
- User complaints about "the cart is broken"

**Phase to address:**
Phase 2 (Optimistic UI implementation) -- UX design decision.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Synthetic cartItemsById entry on optimistic add | Instant quantity controls | Controls fail if server never confirmed; stale data | Never -- use overlay pattern instead |
| Fire-and-forget `void refreshCartState()` | Non-blocking success path | Silent state drift; stale cart badge | Only if reconciliation timer exists as backup |
| New VkusVillCart instance per request | Simple, no shared state | Cookie file re-read overhead; no session reuse | Acceptable at family scale but blocks warmup optimization |
| 2s timer-based state cleanup | Prevents stuck UI states | Hides real failures; races with async confirmations | Acceptable as fallback but should not be primary cleanup |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| VkusVill basket_add.php | Assuming sessid is long-lived | Treat sessid as ephemeral; refresh every 15-30 min |
| VkusVill basket_add.php | Assuming the API is idempotent | It is NOT idempotent -- each call adds +1 quantity. Must prevent duplicate calls. |
| VkusVill basket_recalc.php | Using it as a health check during hot path | It adds 1-3s latency through proxy. Only use for background reconciliation. |
| VkusVill POPUP_ANALOGS response | Treating it as a generic error | It specifically means "product out of stock." Surface this distinctly to the user. |
| __Host-PHPSESSID cookie | Using standard cookie jar libraries | Must use raw Cookie header string -- __Host- prefix cookies break standard parsers |
| ProxyManager rotation | Assuming proxy is always available | `get_working_proxy(allow_refresh=False)` can return None. Direct connection may be geo-blocked from EC2. |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Warmup GET on every cart add | Cart adds consistently >2s | Pre-cache sessid/user_id at login and refresh periodically | Breaks immediately for any user whose sessid expired |
| Full cart refresh after every add | Each add triggers a basket_recalc round-trip | Debounce/coalesce refreshes; use add response data for immediate UI update | Breaks at >3 rapid adds (each queues a refresh) |
| Polling loop with 700ms/900ms intervals | 5s budget only allows 3-4 polls max | Consider websocket or SSE for status push instead of polling | Already at the edge; adding any latency breaks polling |
| Creating httpx.Client per request | Connection setup overhead on each call | Reuse httpx.Client with connection pooling per user session | Noticeable at >5 concurrent cart operations |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Showing green checkmark before server confirms | False confidence; jarring rollback | Neutral pending indicator (pulsing dot) until confirmed |
| Auto-clearing error after 2s timer | User misses the error; re-taps blindly | Keep error visible with explicit retry/dismiss |
| Showing "Корзина временно недоступна" for sessid failures | User thinks VkusVill is down; stops trying | Distinguish session errors ("перезайдите") from VkusVill downtime |
| Cart badge increment on optimistic add | Badge count drifts from reality | Only update badge from server-confirmed cart_items count |
| Silent background reconciliation | User never knows add actually failed | Show a gentle "checking cart..." indicator when reconciling |

## "Looks Done But Isn't" Checklist

- [ ] **Optimistic add:** Verify that opening CartPanel after optimistic add shows the product (not just the main grid card)
- [ ] **Session warmup:** Verify that a user who logged in 2+ hours ago can still add to cart without re-login
- [ ] **Rollback:** Verify that after rollback, the product's cart button returns to the "add" state (not stuck on error)
- [ ] **Double-add prevention:** Verify that rapid double-tap on the same product results in quantity=1, not quantity=2
- [ ] **Cart count:** Verify that cart badge shows correct count after add+rollback sequence
- [ ] **Sold-out handling:** Verify that POPUP_ANALOGS response shows "раскупили" not generic error
- [ ] **Weight products:** Verify that kg-unit products added optimistically show correct step (0.1/0.01) in quantity controls
- [ ] **Background reconciliation:** Verify that a 202-pending that resolves in background eventually updates the UI

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Phantom cart items (optimistic drift) | LOW | Force refreshCartState on CartPanel open; reconcile on any cart interaction |
| Stale sessid | LOW | Detect `success: "N"` + empty error; trigger one-time warmup + retry |
| Double-add | MEDIUM | Detect quantity >1 for new add; offer "remove extra" in UI or auto-correct |
| Cookie file corruption | LOW | VkusVillCart already handles FileNotFoundError; add JSON parse error handling |
| Race between optimistic and refresh | LOW | Generation counter on refreshCartState; discard stale updates |
| Full session expiry (__Host-PHPSESSID invalid) | HIGH | Requires re-login via SMS; surface "сессия истекла, войдите снова" early |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Stale sessid (Pitfall 2) | Phase 1: Diagnose failures | Cart add succeeds for user logged in >1hr ago |
| Session warmup blocking (Pitfall 5) | Phase 1: Diagnose failures | `_ensure_session` takes <50ms when metadata cached |
| Optimistic state divergence (Pitfall 1) | Phase 2: Optimistic UI | Cart badge matches VkusVill real count after add+refresh |
| Double-add (Pitfall 3) | Phase 2: Optimistic UI | Rapid double-tap produces quantity=1 |
| Refresh race condition (Pitfall 4) | Phase 2: Optimistic UI | Adding B while A's refresh is in-flight preserves B's optimistic state |
| Rollback UX (Pitfall 7) | Phase 2: Optimistic UI | Failed add shows retry button, not flash-and-disappear |
| Cookie file race (Pitfall 6) | Phase 3: Session warmup | Concurrent add+quantity for same user both succeed |

## Sources

- Codebase analysis: `cart/vkusvill_api.py`, `backend/main.py`, `miniapp/src/App.jsx`, `miniapp/src/CartPanel.jsx`
- [Solving Optimistic Update Race Conditions in SvelteKit](https://dejan.vasic.com.au/blog/2025/11/solving-optimistic-update-race-conditions-in-sveltekit)
- [React 19 useOptimistic Deep Dive](https://dev.to/a1guy/react-19-useoptimistic-deep-dive-building-instant-resilient-and-user-friendly-uis-49fp)
- [Idempotency: Preventing Double Charges and Duplicate Actions](https://dzone.com/articles/art-of-idempotency-preventing-double-charges-and-duplicate)
- [How Optimistic Updates Make Apps Feel Faster](https://blog.openreplay.com/optimistic-updates-make-apps-faster/)
- [Implementing Idempotency - Shopify](https://shopify.dev/docs/api/usage/implementing-idempotency)
- [PHP Session Timeouts Best Practices](https://www.w3tutorials.net/blog/session-timeouts-in-php-best-practices/)
- VkusVill integration observations from existing codebase comments and KEY DECISIONS table

---
*Pitfalls research for: v1.13 Instant Cart & Reliability*
*Researched: 2026-04-08*

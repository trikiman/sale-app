# Feature Research: Instant Cart & Reliability (v1.13)

**Domain:** Optimistic cart UX, error recovery, session warmup for e-commerce cart proxy
**Researched:** 2026-04-08
**Confidence:** HIGH (domain patterns well-established; project-specific constraints thoroughly documented in v1.11/v1.12 context)

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = cart feels broken or untrustworthy.

| Feature | Why Expected | Complexity | Dependencies | Notes |
|---------|--------------|------------|--------------|-------|
| **Diagnose current cart failures** | Users see spinner then error on every add; nothing works until root cause is found | MEDIUM | Access to production logs, backend/main.py cart endpoint | Must happen FIRST. Optimistic UI on a broken backend is cosmetic. Current symptom: add requests take 3-4s, then timeout or error. Could be session expiry, proxy routing, VkusVill API changes, or warmup blocking the hot path. |
| **Immediate visual feedback on tap** | Every grocery app (VkusVill, Instacart, Ozon) shows instant button state change on tap. A 1-4s spinner is unacceptable by 2026 standards | LOW | Existing `cartStates` state machine in App.jsx | Standard optimistic UI: update button state and cart count instantly, fire API call in background. The cart count badge and button state should change within the same animation frame as the tap. |
| **Success confirmation** | Users need to know the item actually landed in their VkusVill cart | LOW | Existing toast system, existing `refreshCartState()` | Already have checkmark + toast. Keep them. Optimistic success followed by silent server confirmation is the standard pattern. |
| **Clear error messages** | When VkusVill is genuinely down, user should know it is a VkusVill problem, not a bug in the app | LOW | Existing toast system | Current messages ("Корзина временно недоступна") are already decent. Distinguish between "sold out", "session expired", "VkusVill down", and "network error". |
| **Retry capability after error** | Users expect to tap again after a transient error. Button should return to tappable state quickly | LOW | Existing 2s timeout on error state | Already implemented (error state clears after 2s). Keep this. |
| **Cart count stays accurate** | If optimistic add fails, cart count must revert. Users notice phantom count increases | MEDIUM | `cartCount`, `cartItemIds`, `cartItemsById` state | Rollback is the heart of optimistic UI. Snapshot pre-tap state, revert on failure. The existing `refreshCartState(1, 0)` call after success can serve as ground-truth reconciliation. |

### Differentiators (Competitive Advantage)

Features that go beyond what users expect. These make the cart experience feel premium.

| Feature | Value Proposition | Complexity | Dependencies | Notes |
|---------|-------------------|------------|--------------|-------|
| **Optimistic add with background reconciliation** | Tap = instant success. API confirms silently in background. Revert only on confirmed failure. This is what VkusVill's own app does | MEDIUM | Diagnostic fix (table stakes), state snapshot/rollback logic | Core v1.13 differentiator. Current flow: tap -> spinner 1-5s -> checkmark/error. Target flow: tap -> instant checkmark -> background API -> silent confirm OR gentle revert with toast. |
| **Session warmup pre-caching** | Eliminate the warmup GET that blocks first cart add after app open. Pre-cache sessid + user_id on app load or login, not on first cart tap | MEDIUM | `cart/vkusvill_api.py` metadata caching, backend session endpoint | Currently `_extract_session_params()` does a full page GET to VkusVill if sessid/user_id are not in cookie metadata. This adds 1-2s to the first add. Pre-warming on app load makes every add fast, not just the second one. |
| **Graceful degradation for ambiguous timeouts** | Instead of hard error on timeout, show neutral "checking cart" state that resolves in background. App stays usable | LOW | Existing `pending` state from v1.11, existing `pollCartAttemptStatus` | Already partially built in v1.11/v1.12. The improvement is: with optimistic UI, the pending/timeout path only fires on confirmed failure after the background reconciliation check, not as the primary user-visible state. |
| **Cross-surface cart state sync** | If user adds from product card, detail drawer shows in-cart control immediately (and vice versa) | LOW | Existing shared `cartStates`/`cartItemsById` in App.jsx | Already works for non-optimistic flow since card and detail share state. Optimistic state just needs to flow through the same mechanism. No extra work beyond the optimistic state update itself. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems in this specific context.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Full React 19 useOptimistic hook** | Modern React pattern for optimistic UI | App is on Vite + React (not React 19 with Server Actions). useOptimistic requires React 19 and is designed for form actions/transitions, not imperative async calls. Introducing it means a React version upgrade + architecture change for marginal benefit | Simple state snapshot + rollback with existing useState/useCallback. The pattern is identical in behavior: save previous state, update optimistically, revert on error. 15 lines of code vs a framework migration. |
| **Offline cart queue** | Let users add to cart without internet, sync when online | VkusVill cart is server-authoritative. Items can be sold out between offline add and sync. Creates false promises. Also, this is a Telegram MiniApp — no ServiceWorker, limited offline capability | Show clear "no connection" error. The app is inherently online-only (scrapes live prices). |
| **Automatic retry on failure** | Retry the VkusVill API call automatically N times | VkusVill bans concurrent connections and has anti-bot measures. Automatic retries risk triggering rate limits or bans. Also, if VkusVill is genuinely down, retries just burn proxy pool for nothing | Manual retry via tapping again. The button returns to tappable state after 2s error display. User decides whether to retry. Backend dedupe protects against accidental double-taps within 5s window. |
| **Speculative pre-add (add before tap)** | Predict which items user will add and pre-warm the add request | Absurd for a grocery discount aggregator. Users browse dozens of items and add few. Speculative API calls would waste VkusVill session budget and risk bans | Session warmup (pre-cache sessid) is sufficient. The add call itself is fast (~200-400ms) when the session is warm. The latency problem is warmup, not the add. |
| **Real-time cart sync via WebSocket** | Push cart changes from server to client instantly | Adds server complexity for a 5-user family app. The existing SSE + 60s polling for products is sufficient. Cart state is already refreshed after add/modify operations | `refreshCartState()` after optimistic success is enough. Cart changes only happen from user actions in this app. |
| **Persistent pending state across app restarts** | Remember that an add was in-flight if user closes and reopens MiniApp | Telegram MiniApp lifecycle is unpredictable. Stale pending state from a previous session would confuse users. The 5s hard cap means pending states are transient by design | On app reopen, just fetch fresh cart state from VkusVill. Any previously-pending adds will have resolved (succeeded or failed) by then. |

## Feature Dependencies

```
[Diagnose cart failures]
    └── required by ──> [Optimistic cart UX]
                            ├── enhances ──> [Session warmup pre-caching]
                            │                    (warmup makes optimistic add faster on first tap)
                            └── enhances ──> [Graceful degradation for ambiguous timeouts]
                                                 (optimistic UI makes the timeout path rare and less visible)

[Session warmup pre-caching]
    └── independent of ──> [Optimistic cart UX]
        (can ship separately; reduces latency even without optimistic UI)

[Cross-surface cart state sync]
    └── requires ──> [Optimistic cart UX]
        (sync is only meaningful when optimistic state is being shown)

[Clear error recovery with retry]
    └── independent of ──> [Optimistic cart UX]
        (error messages and retry work regardless of whether add is optimistic)
    └── enhanced by ──> [Diagnose cart failures]
        (once failures are diagnosed, error messages can be more specific)
```

### Dependency Notes

- **Diagnose cart failures MUST come first:** Optimistic UI on a broken cart backend creates the worst possible UX -- instant success followed by revert on every single add. Fix the actual failures before adding optimistic behavior.
- **Session warmup is independently valuable:** Even without optimistic UI, eliminating the warmup GET saves 1-2s on every first add. Can be developed in parallel with diagnosis.
- **Optimistic UI and error recovery are complementary:** Optimistic UI reduces the visible impact of slow adds; error recovery handles the case where adds actually fail. Together they cover the full spectrum.

## MVP Definition

### Must Ship (v1.13 scope)

These are the four features in the active requirements:

- [x] **Diagnose and fix cart add failures** -- Without this, nothing else matters. Current state: spinner -> error on most/all adds.
- [x] **Optimistic cart UX** -- Immediate visual success on tap, background API call, revert on failure. The core user-facing improvement.
- [x] **Session warmup optimization** -- Pre-cache sessid/user_id to eliminate hot-path blocking. Reduces first-add latency from 3-4s to <1s.
- [x] **Clear error recovery with retry** -- When VkusVill is genuinely unavailable, show clear message and let user retry.

### Already Built (from v1.11/v1.12)

These exist and should be preserved, not rebuilt:

- [x] 5s hard cap via AbortController (v1.12 CART-10..14)
- [x] Pending/polling system with time-budget loop (v1.11/v1.12)
- [x] Background cart reconciliation after ambiguous timeouts (v1.11)
- [x] Backend dedupe for same user+product within 5s window (v1.11)
- [x] Cart panel with spinner/checkmark/X feedback (existing)
- [x] In-cart quantity controls (pill widget, step by unit) (v1.11 Phase 44)
- [x] Toast notifications for cart feedback (existing)

### Defer (post-v1.13)

- [ ] **Haptic feedback on add** -- Nice touch but not in scope. Telegram MiniApp may not support it reliably.
- [ ] **Cart total price preview** -- Useful but separate feature. Current cart panel shows items but not running total.
- [ ] **Undo add** -- Complicates the optimistic flow. Remove from cart panel serves the same purpose.
- [ ] **Batch add multiple items** -- Not needed for a discount aggregator where users cherry-pick items.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Risk | Priority | Phase Order |
|---------|------------|---------------------|------|----------|-------------|
| Diagnose cart failures | HIGH | MEDIUM (requires prod log analysis) | HIGH if skipped | P0 | 1st |
| Session warmup pre-caching | HIGH | LOW (metadata already cached in cookie files; just need earlier loading) | LOW | P1 | Can parallel with diagnosis |
| Optimistic cart UX | HIGH | MEDIUM (state snapshot + rollback + cart count revert) | MEDIUM (rollback edge cases) | P1 | After diagnosis fix |
| Error recovery UX refinement | MEDIUM | LOW (better messages, keep existing retry-via-retap) | LOW | P2 | After optimistic UI |

**Priority key:**
- P0: Must fix first, blocks everything
- P1: Core milestone value
- P2: Polish and robustness

## Competitor/Reference Feature Analysis

| Feature | VkusVill Native App | Instacart / Samokat | Our Current State | v1.13 Target |
|---------|---------------------|---------------------|-------------------|--------------|
| Add-to-cart latency | ~100ms (optimistic) | ~100ms (optimistic) | 1-5s (synchronous) | ~100ms (optimistic) |
| Button state on tap | Instant pill switch | Instant counter | Spinner 1-5s | Instant checkmark |
| Cart count update | Instant | Instant | After API response | Instant (optimistic) |
| Failure handling | Gentle revert + toast | Gentle revert + toast | Red X after 5s | Gentle revert + toast |
| Session warmup | Transparent (native auth) | Transparent (native auth) | Blocks first add 1-2s | Pre-cached on app load |
| Retry after failure | Tap button again | Tap button again | Tap after 2s error clears | Same (keep existing) |
| Sold-out feedback | "Нет в наличии" badge | "Out of stock" badge | Toast + sold-out tracking | Same (keep existing) |

## Implementation Patterns (Research Findings)

### Optimistic Cart Add Pattern

The standard optimistic UI pattern for cart operations, well-documented across React ecosystem:

1. **Snapshot** current cart state (count, itemIds, itemsById)
2. **Update optimistically** -- set cart count +1, add product to itemIds/itemsById, show success state
3. **Fire API call** in background (no spinner, no blocking)
4. **On API success** -- do nothing visible (already showing success). Optionally refresh cart from server for ground truth
5. **On API failure** -- revert to snapshot, show brief error toast, return button to tappable state

**Key rule from research:** "Rollback is the heart of optimistic UI. Omitting the rollback logic will cause adverse consequences." The snapshot-before-update pattern is non-negotiable.

**This project's specific twist:** The VkusVill API is slow (1-4s typical) and sometimes returns ambiguous pending states. The optimistic UI should treat the 5s timeout path as "background check" rather than error, and only revert on confirmed failure.

### Session Warmup Pattern

Standard "cache warming" adapted for this project's session model:

1. **On app load / login** -- fire a low-priority request to backend that triggers `_extract_session_params()` in advance
2. **Cache sessid + user_id** in the cookie metadata JSON file so subsequent `VkusVillCart.__init__()` finds them without a warmup GET
3. **TTL the cache** -- sessid/user_id are session-scoped, valid as long as cookies are valid. Invalidate on logout/re-login.

**This project's constraint:** The warmup GET goes to VkusVill (not our backend), so it costs a proxy connection and ~1-2s. Running it on app load means the cost is amortized before the user ever taps "add to cart."

### Error Recovery Pattern

Standard e-commerce error recovery:

1. **Transient errors** (timeout, network) -- brief error display (2-3s), return to normal state, user can retry
2. **Sold-out errors** -- persistent badge/state, do not allow retry (item genuinely unavailable)
3. **Session errors** (401) -- redirect to login, do not show cart error
4. **Unknown errors** -- brief generic error, return to normal, allow retry

**This project already implements most of this.** The v1.13 refinement is: with optimistic UI, the error path is "revert optimistic success + show error toast" rather than "clear spinner + show error X."

## Sources

- [React useOptimistic Hook documentation](https://react.dev/reference/react/useOptimistic)
- [Optimistic UI Updates in React (freeCodeCamp)](https://www.freecodecamp.org/news/how-to-use-the-optimistic-ui-pattern-with-the-useoptimistic-hook-in-react/)
- [Optimistic Updates Make Apps Faster (OpenReplay)](https://blog.openreplay.com/optimistic-updates-make-apps-faster/)
- [Shopping Cart UX Design (JustInMind)](https://www.justinmind.com/ui-design/shopping-cart)
- [WooCommerce Cart Race Conditions PR](https://github.com/woocommerce/woocommerce/pull/63120)
- [Cache Warming Best Practices (ioriver)](https://www.ioriver.io/terms/cache-warming)
- [E-commerce UX Best Practices 2026 (instinctools)](https://www.instinctools.com/blog/ecommerce-ux-best-practices/)
- [Understanding Optimistic UI (LogRocket)](https://blog.logrocket.com/understanding-optimistic-ui-react-useoptimistic-hook/)

---
*Feature research for: v1.13 Instant Cart & Reliability*
*Researched: 2026-04-08*

# Project Research Summary

**Project:** VkusVill Sale Monitor -- v1.13 Instant Cart and Reliability
**Domain:** Optimistic cart UX, session reliability, error recovery for e-commerce cart proxy
**Researched:** 2026-04-08
**Confidence:** HIGH

## Executive Summary

The v1.13 milestone targets the cart experience -- the slowest, most fragile part of the app. Currently, every add-to-cart triggers a 1-5 second synchronous spinner, and many adds fail silently due to stale session tokens or session warmup blocking the hot path. The research identifies stale sessid tokens (Bitrix CSRF rotation) and `_ensure_session()` warmup GETs blocking the 1.5s hot-path deadline as the two most likely root causes of current failures. Both are fixable without new dependencies.

The recommended approach is a four-phase build: (1) diagnose and fix the actual backend failures before touching UI, (2) move session warmup off the cart-add hot path, (3) implement optimistic cart UX with snapshot-and-revert, (4) refine error recovery messaging. The stack changes are minimal -- one small npm package (`react-error-boundary`) and zero new backend dependencies. React 19 built-in `useOptimistic` is available but the FEATURES research flags it as an anti-feature in this context: the existing `handleAddToCart` is 130 lines of imperative logic (AbortController, polling, budget tracking) that does not fit the `useOptimistic` + Server Actions model. A simpler snapshot-and-revert pattern using existing `useState` hooks is the right choice.

The primary risk is optimistic state divergence -- showing items as "in cart" when VkusVill never confirmed the add. This creates phantom cart items that vanish at checkout. The mitigation is strict: never add synthetic entries to `cartItemsById`, use an overlay pattern for display, reconcile against server state within 10 seconds, and always revert on non-confirmed paths. The secondary risk is double-adds from retry overlap (VkusVill `basket_add.php` is NOT idempotent), mitigated by a product-scoped cooldown and extended backend dedupe window.

## Key Findings

### Recommended Stack

No major additions needed. The existing React 19.2.0 + FastAPI + httpx stack is sufficient. See [STACK.md](STACK.md) for full details.

**Core technologies:**
- **React `useOptimistic` / `startTransition`** (already installed, React 19.2.0): Optimistic visual state layer only -- the imperative cart flow stays as-is
- **`react-error-boundary` ^6.1.1** (NEW, 5.6KB): Catch render crashes in cart/product components; the app currently has zero error boundaries
- **Persistent `httpx.AsyncClient`** (already installed): Reuse TCP connections to VkusVill instead of creating new clients per request, saving 200-500ms TLS overhead
- **Python dict session cache** (no new dep): Cache initialized `VkusVillCart` instances per user with 10-min TTL and mtime-based invalidation
- **Hand-rolled retry utility** (no new dep): 20-line `retryWithBackoff` respecting the existing 5s AbortController budget

**What NOT to add:** Zustand/Redux (overkill), TanStack Query (3 endpoints), Redis (5 users), Sentry (family app), WebSocket (SSE + polling already works), Service Workers (Telegram MiniApp limitation).

### Expected Features

See [FEATURES.md](FEATURES.md) for full analysis including competitor comparison.

**Must have (table stakes):**
- Diagnose and fix current cart add failures -- nothing else matters if adds keep failing
- Immediate visual feedback on tap -- every competitor does this; a 1-5s spinner is unacceptable in 2026
- Success confirmation -- user must know the item actually landed in VkusVill cart
- Clear error messages distinguishing sold-out / session expired / VkusVill down / network error
- Cart count accuracy -- optimistic count must revert on failure, not drift

**Should have (differentiators):**
- Optimistic add with background reconciliation -- tap = instant success, silent server confirm, gentle revert on failure
- Session warmup pre-caching -- eliminate the 1-2s warmup GET that blocks first add after app open
- Graceful degradation for ambiguous timeouts -- "checking cart" state instead of hard error

**Defer (post-v1.13):**
- Haptic feedback on add (Telegram MiniApp support uncertain)
- Cart total price preview (separate feature)
- Undo add (remove-from-cart already serves this purpose)
- Batch add multiple items (not needed for cherry-pick discount browsing)

### Architecture Approach

All cart state lives in `App.jsx` as top-level `useState` hooks, prop-drilled to `ProductCard`, `ProductDetail`, and `CartPanel`. This is correct for a 5-user family app -- no state library needed. The optimistic UI layer adds a `revertCartOptimistic()` helper and modifies `handleAddToCart` to update state immediately before firing the API call. Session warmup hooks into the existing `/api/auth/status` endpoint as a `BackgroundTask` side-effect, requiring zero frontend changes. See [ARCHITECTURE.md](ARCHITECTURE.md) for full data flow diagrams.

**Major components modified:**
1. **`cart/vkusvill_api.py`** -- Add structured error types, sessid staleness detection, diagnostic timing logs
2. **`backend/main.py`** -- Session warmup as BackgroundTask on auth check, structured error responses from cart endpoints, VkusVillCart instance caching per user with TTL
3. **`miniapp/src/App.jsx`** -- Optimistic state updates in `handleAddToCart`, snapshot-and-revert helper, error-type-specific toast messages
4. **No new components created** -- all changes are modifications to existing files

### Critical Pitfalls

See [PITFALLS.md](PITFALLS.md) for all 7 pitfalls with detailed prevention strategies.

1. **Optimistic state diverges from real basket** -- Never add synthetic entries to `cartItemsById`; use an overlay pattern. Reconcile against server state within 10s. Revert on any non-confirmed path.
2. **Stale sessid causes silent failures** -- Add `sessid_saved_at` timestamp; treat sessid as stale after 30 min. On `success: "N"` with no POPUP_ANALOGS, retry once with fresh sessid. This is likely the root cause of current cart failures.
3. **Double-add from retry overlap** -- VkusVill `basket_add.php` is NOT idempotent. Add product-scoped cooldown (8-10s) on frontend. Extend backend dedupe window to 10s keyed on (user_id, product_id) regardless of client_request_id.
4. **Race between optimistic state and refreshCartState** -- Maintain an `optimisticPending` set. When `refreshCartState` returns, merge server state with in-flight optimistic entries instead of full replacement. Use a generation counter to discard stale updates.
5. **Session warmup blocks the hot path** -- Move `_ensure_session()` entirely out of the `add()` deadline. If sessid is missing at add-time, fail fast with `session_needs_warmup` and trigger async warmup. Never call `_extract_session_params` inside the 1.5s deadline.

## Implications for Roadmap

Based on combined research, the milestone decomposes into 4 phases with strict ordering driven by dependencies.

### Phase 1: Diagnose and Fix Cart Failures
**Rationale:** Every other phase builds on a working cart backend. Optimistic UI on a broken backend creates the worst possible UX -- instant success followed by 100% revert rate. The research strongly indicates stale sessid and warmup-blocking-hot-path as root causes.
**Delivers:** Reliable cart adds with structured error types; diagnostic logging; sessid staleness detection and auto-refresh.
**Addresses:** Table stakes (diagnose failures, clear error messages). Features P0.
**Avoids:** Pitfall 2 (stale sessid), Pitfall 5 (warmup blocking hot path).
**Modifies:** `cart/vkusvill_api.py`, `backend/main.py` cart endpoints.
**Estimated scope:** MEDIUM -- requires production log analysis + targeted fixes.

### Phase 2: Session Warmup Optimization
**Rationale:** Independently valuable (saves 1-2s on first add), and makes Phase 3 optimistic UI more reliable because backend responds faster. Can partially overlap with Phase 1 diagnosis.
**Delivers:** Pre-cached sessid/user_id on app load; zero warmup latency on cart-add hot path; VkusVillCart instance caching per user with TTL.
**Addresses:** Differentiator (session warmup pre-caching). Features P1.
**Avoids:** Pitfall 5 (warmup blocking), Pitfall 6 (cookie file race via instance caching).
**Modifies:** `backend/main.py` (auth status endpoint + new warmup function).
**Estimated scope:** LOW-MEDIUM -- clear implementation path via BackgroundTask on auth check.

### Phase 3: Optimistic Cart UX
**Rationale:** The core user-facing improvement. Requires Phase 1 (working backend) and benefits from Phase 2 (fast backend). This is where the UI transforms from "spinner for 1-5s" to "instant success."
**Delivers:** Instant visual feedback on tap; snapshot-and-revert on failure; cart count accuracy through reconciliation; optimistic overlay pattern.
**Addresses:** Table stakes (immediate feedback, cart count accuracy). Differentiators (optimistic add, cross-surface sync). Features P1.
**Avoids:** Pitfall 1 (state divergence), Pitfall 3 (double-add), Pitfall 4 (refresh race), Pitfall 7 (whack-a-mole rollback UX).
**Modifies:** `miniapp/src/App.jsx` only.
**Estimated scope:** MEDIUM -- significant logic changes to handleAddToCart, but contained to one file.

### Phase 4: Error Recovery UX
**Rationale:** Depends on structured error types from Phase 1 and optimistic revert from Phase 3. This is polish that makes failure paths clear and actionable.
**Delivers:** Error-type-specific messages (sold out vs session expired vs VkusVill down); retry action on error toasts; error boundary wrapping for cart/product components.
**Addresses:** Table stakes (clear error messages, retry capability). Features P2.
**Avoids:** Pitfall 7 (rollback UX confusion) -- inline retry buttons instead of flash-and-disappear.
**Modifies:** `miniapp/src/App.jsx`, adds `react-error-boundary` wrapping.
**Estimated scope:** LOW -- mostly message strings and toast actions; error boundary is straightforward.

### Phase Ordering Rationale

- **Phase 1 before everything:** All researchers agree -- diagnosis must come first. FEATURES.md marks it P0 ("blocks everything"). PITFALLS.md identifies stale sessid as the likely root cause. ARCHITECTURE.md confirms the failure flow and where to instrument.
- **Phase 2 before Phase 3:** Session warmup reduces backend latency, which directly reduces optimistic revert rate. A fast backend means fewer reverts, which means better UX.
- **Phase 3 before Phase 4:** Error recovery messaging depends on the optimistic revert flow (Phase 3) and structured error types (Phase 1). Building error UX before the optimistic flow exists means reworking it.
- **Phases 1-2 are backend-only; Phases 3-4 are frontend-only.** This is a clean separation that allows backend work to be deployed and validated before touching the UI.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1:** Needs production log analysis to confirm stale sessid hypothesis. May uncover additional failure modes not visible in code review alone. Recommend `/gsd-research-phase` with access to production logs.
- **Phase 3:** The optimistic overlay pattern (separate from `cartItemsById`) needs careful design to avoid breaking `CartPanel`, `CartQuantityControl`, and `ProductDetail` which all read from `cartItemsById`. Recommend `/gsd-research-phase` to map all consumers of cart state.

Phases with standard patterns (skip research-phase):
- **Phase 2:** Session warmup via BackgroundTask is a well-documented FastAPI pattern. Implementation path is clear from ARCHITECTURE.md.
- **Phase 4:** Error boundary setup and toast messaging are standard React patterns. No research needed.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Minimal additions; React 19 APIs verified against official docs; httpx patterns well-documented |
| Features | HIGH | Grounded in existing v1.11/v1.12 architecture; competitor analysis confirms expectations |
| Architecture | HIGH | Based on direct codebase analysis of actual files; data flows traced through code |
| Pitfalls | HIGH | Codebase-grounded; specific line numbers cited; VkusVill API behavior observed firsthand |

**Overall confidence:** HIGH

### Gaps to Address

- **Root cause confirmation:** The stale sessid hypothesis (Pitfall 2) is strongly supported by code analysis but not yet confirmed against production logs. Phase 1 planning should include a diagnostic step.
- **VkusVill sessid rotation frequency:** Research could not determine exact TTL for Bitrix CSRF tokens. The 30-minute staleness threshold is a conservative estimate. May need adjustment based on production observation.
- **useOptimistic vs manual snapshot:** STACK.md recommends `useOptimistic` for the visual layer; FEATURES.md flags it as an anti-feature due to the imperative flow. Recommendation: start with manual snapshot-and-revert (simpler, no architecture change), evaluate `useOptimistic` as a refinement if the manual approach proves cumbersome.
- **Proxy reliability during warmup:** Session warmup GETs go through the proxy. If proxy is unavailable, warmup silently fails and the next cart add hits the slow path. Phase 2 should handle proxy-unavailable gracefully.

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis: `cart/vkusvill_api.py`, `backend/main.py`, `miniapp/src/App.jsx`, `miniapp/src/CartPanel.jsx`, `miniapp/src/ProductDetail.jsx`, `miniapp/src/CartQuantityControl.jsx`
- [React useOptimistic official docs](https://react.dev/reference/react/useOptimistic)
- [React 19 release blog](https://react.dev/blog/2024/12/05/react-19)
- [httpx Client documentation](https://www.python-httpx.org/advanced/clients/)
- [react-error-boundary npm](https://www.npmjs.com/package/react-error-boundary)
- PROJECT.md key decisions table (metadata-first cart session bootstrap, opt-in pending cart add contract)

### Secondary (MEDIUM confidence)
- [Optimistic UI Patterns -- freeCodeCamp](https://www.freecodecamp.org/news/how-to-use-the-optimistic-ui-pattern-with-the-useoptimistic-hook-in-react/)
- [Optimistic Updates -- OpenReplay](https://blog.openreplay.com/optimistic-updates-make-apps-faster/)
- [Idempotency Patterns -- Shopify](https://shopify.dev/docs/api/usage/implementing-idempotency)
- [Cache Warming Best Practices -- ioriver](https://www.ioriver.io/terms/cache-warming)
- [Solving Optimistic Update Race Conditions -- SvelteKit](https://dejan.vasic.com.au/blog/2025/11/solving-optimistic-update-race-conditions-in-sveltekit)

### Tertiary (LOW confidence)
- VkusVill Bitrix CMS sessid rotation behavior -- inferred from code patterns, not documented by VkusVill
- PHP session timeout defaults -- general Bitrix/PHP knowledge, may not match VkusVill specific configuration

---
*Research completed: 2026-04-08*
*Ready for roadmap: yes*

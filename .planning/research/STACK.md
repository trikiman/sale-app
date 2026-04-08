# Technology Stack: v1.13 Instant Cart & Reliability

**Project:** VkusVill Sale Monitor
**Researched:** 2026-04-08
**Scope:** Stack additions for optimistic cart UX, failure diagnosis, session warmup, error recovery

## Recommended Stack Additions

### Frontend: Optimistic Updates

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| React `useOptimistic` | 19.2.0 (already installed) | Optimistic cart state on tap | Built into React 19. No new dependency. Automatically reverts to real state when transition completes or fails. The app already uses React 19.2.0 so this is free. |
| React `startTransition` | 19.2.0 (already installed) | Wrap async cart calls | Required companion for `useOptimistic`. Marks the async cart add as a transition so React keeps showing optimistic state until resolution. |

**Why NOT useOptimistic alone:** The current `handleAddToCart` is ~130 lines of imperative logic (AbortController, 5s budget, pending polling, sold-out detection, toast messages). `useOptimistic` handles the "show success immediately, revert on failure" part, but the existing imperative flow for polling/timeout/error-classification must remain. Use `useOptimistic` for the visual state layer only, keep the existing control flow.

**Integration pattern:**
```jsx
const [optimisticCartIds, addOptimisticCartId] = useOptimistic(
  cartItemIds,
  (currentIds, newId) => {
    const next = new Set(currentIds);
    next.add(String(newId));
    return next;
  }
);

// In handleAddToCart, before fetch:
startTransition(async () => {
  addOptimisticCartId(product.id);
  // ...existing fetch + polling logic...
  // On success: setCartItemIds updates real state, optimistic merges
  // On failure: transition ends, optimistic reverts automatically
});
```

### Frontend: Error Boundaries

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `react-error-boundary` | ^6.1.1 | Catch render crashes in cart/product components | 5.6KB gzipped. Provides `ErrorBoundary` with `fallbackRender`, `onReset`, and `resetKeys` props. The app currently has zero error boundaries -- a render crash in CartPanel or ProductDetail kills the whole app. |

**Why this library over hand-rolled:** React error boundaries require class components. `react-error-boundary` wraps that in a functional API with `useErrorBoundary()` hook for imperative error throwing from event handlers. The `resetKeys` prop auto-resets the boundary when deps change (e.g., when user retries). Maintained by Brian Vaughn (former React team).

**What NOT to add:** Do NOT add Sentry, LogRocket, or any error monitoring service. This is a 5-user family app. Console logs and the existing admin panel diagnostics are sufficient.

### Frontend: Retry Logic

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Hand-rolled retry utility | N/A | Retry failed cart adds with backoff | Do NOT add `exponential-backoff` or `retry-axios` npm packages. The existing cart add flow is already deeply custom (AbortController, 5s hard cap, pending polling, budget-aware loops). A generic retry library would fight the existing architecture. Instead, write a 20-line `retryWithBackoff(fn, { maxAttempts: 2, baseDelay: 1000, signal })` utility that respects the AbortController budget. |

**Rationale against library:** The 5s hard cap means max 1 retry (first attempt ~2-3s, retry ~2s). A library adds complexity for a pattern that needs exactly 2 attempts with budget-aware timeout. The existing `pollCartAttemptStatus` already implements budget-aware looping -- extend that pattern.

### Backend: Session Warmup / Caching

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `httpx.AsyncClient` (persistent) | Already installed (httpx >=0.27.0) | Reuse TCP connections to VkusVill | Current code creates a new `httpx.Client` per request in `VkusVillCart._request()`. This wastes ~200-500ms on TLS handshake every call. A persistent client with connection pooling eliminates this. |
| `VkusVillCart` instance cache | Pure Python dict | Cache initialized cart instances per user | Current code: every `/api/cart/add` creates `VkusVillCart(cookies_path=...)` which runs `_ensure_session()` including a potential GET to vkusvill.ru (~2-3s). Cache the initialized instance keyed by `(telegram_user_id, cookies_mtime)` with 10-min TTL. Invalidate on cookie file change. |

**Session warmup strategy (backend, no new deps):**
1. On app startup or first cart request per user: initialize `VkusVillCart`, call `_ensure_session()`, cache the instance
2. On subsequent requests: reuse cached instance (sessid + user_id + cookie_str already loaded)
3. TTL: 10 minutes (VkusVill sessions last hours, but cookie files may change on re-login)
4. Invalidation: check `os.path.getmtime(cookies_path)` vs cached mtime

**Why NOT Redis/Memcached:** 5-user family app on t3.micro with 1GB RAM. A Python dict with TTL is sufficient. Adding Redis would consume ~50MB RAM and add operational complexity for zero benefit at this scale.

### Backend: Background Retry for Pending Adds

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `asyncio.create_task` | Python stdlib | Fire-and-forget background retry after timeout | Already available. When VkusVill times out on hot path (1.5s), spawn a background task that retries once with a longer timeout (5s). Update the attempt store on success/failure. No new dependency needed. |

## What NOT to Add

| Technology | Why Not |
|------------|---------|
| Zustand / Jotai / Redux | Overkill. The app manages cart state with `useState` + `useCallback` in App.jsx. Optimistic updates need `useOptimistic` (built-in), not a state management library. The cart state is local to one component tree. |
| TanStack Query / SWR | The app has exactly 3 fetch patterns (products list, cart items, cart add). Adding a data-fetching library for 3 endpoints adds 30KB+ for cache invalidation logic the app does not need. The existing `refreshCartState()` with manual cache is fine. |
| `retry-axios` / `p-retry` / `exponential-backoff` | Generic retry fights the 5s hard cap + budget-aware polling architecture. Custom 20-line utility is better. |
| Sentry / error monitoring | 5-user family app. Console logs + admin panel diagnostics suffice. |
| Redis / Memcached | Session cache in Python dict with TTL is sufficient at 5-user scale. |
| `react-query` for optimistic mutations | `useOptimistic` is built into React 19 and purpose-built for this. |
| WebSocket for cart updates | SSE + polling already handles product updates. Cart truth recovery already uses polling. Adding WebSocket for cart-only pushes is overengineered. |
| Service Worker for offline retry | This is a Telegram MiniApp -- service workers have limited support in embedded WebViews. Not worth the complexity. |

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Optimistic UI | `useOptimistic` (React 19 built-in) | Zustand optimistic middleware | Extra dependency, React 19 solves this natively |
| Error boundaries | `react-error-boundary` ^6.1.1 | Hand-rolled class component | Library is 5.6KB, provides hooks + resetKeys for free |
| Cart retry | Hand-rolled utility | `exponential-backoff` npm | 5s budget means max 1 retry; library is overkill |
| Session cache | Python dict + mtime check | Redis | 5 users, 1GB RAM server, dict is sufficient |
| HTTP client reuse | Persistent `httpx.Client` singleton | Connection pool library | httpx already has built-in connection pooling |

## Installation

```bash
# Frontend (in miniapp/)
npm install react-error-boundary@^6.1.1

# Backend -- no new packages needed
# All changes use existing httpx, asyncio, and Python stdlib
```

## Confidence Assessment

| Item | Confidence | Source |
|------|------------|--------|
| `useOptimistic` API + behavior | HIGH | Official React docs (react.dev/reference/react/useOptimistic) |
| `react-error-boundary` compatibility with React 19 | HIGH | npm registry shows v6.1.1 with React 19 peer dep |
| httpx persistent client perf improvement | HIGH | Official httpx docs (python-httpx.org/advanced/clients) |
| Session warmup via instance caching | MEDIUM | Pattern is straightforward but VkusVill session invalidation behavior is not fully documented |
| Hand-rolled retry over library | HIGH | Architecture constraint (5s hard cap) makes generic retry libraries counterproductive |

## Sources

- [React useOptimistic official docs](https://react.dev/reference/react/useOptimistic)
- [React 19 release blog](https://react.dev/blog/2024/12/05/react-19)
- [react-error-boundary npm](https://www.npmjs.com/package/react-error-boundary)
- [httpx Client documentation](https://www.python-httpx.org/advanced/clients/)
- [httpx AsyncClient patterns](https://medium.com/@sparknp1/8-httpx-asyncio-patterns-for-safer-faster-clients-f27bc82e93e6)
- [exponential-backoff npm](https://www.npmjs.com/package/exponential-backoff)

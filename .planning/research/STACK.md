# Technology Stack: v1.13 Instant Cart & Reliability

**Project:** VkusVill Sale Monitor
**Researched:** 2026-04-08
**Scope:** Stack additions for optimistic cart UX, session warmup, error recovery

## Key Finding: Nearly Zero New Dependencies

React 19 (`^19.2.0` in package.json) ships `useOptimistic` natively. Backend already has session metadata persistence (`sessid`/`user_id` in cookie JSON files). The only new package is `react-error-boundary` for crash resilience. Everything else is refactoring existing code.

## Recommended Stack (Changes Only)

### Frontend: Optimistic Updates — No New Packages

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| React `useOptimistic` | 19.2.0 (already installed) | Optimistic cart state on tap | Built into React 19. Automatically reverts to real state when async action completes or fails. |
| React `startTransition` | 19.2.0 (already installed) | Wrap async cart calls | Required companion for `useOptimistic`. Keeps optimistic state visible until resolution. |

**Why NOT useOptimistic alone:** Current `handleAddToCart` in App.jsx (lines 892-1019) is ~130 lines of imperative logic: AbortController, 5s budget, pending polling, sold-out detection. `useOptimistic` handles the visual layer ("show success immediately, revert on failure") but the existing imperative control flow for polling/timeout must remain alongside it.

**Integration pattern:**
```jsx
const [optimisticCartIds, addOptimisticCartId] = useOptimistic(
  cartItemIds,  // real state from server
  (currentIds, newId) => new Set([...currentIds, String(newId)])
);

// In handleAddToCart, before fetch:
startTransition(async () => {
  addOptimisticCartId(product.id);  // instant visual success
  // ...existing fetch + polling logic unchanged...
  // On success: real state updates, optimistic merges naturally
  // On failure: transition ends, optimistic reverts automatically
});
```

**Cart state machine migration:** Replace current `cartStates` (`useState` object with per-product `loading|pending|success|error|null`) with `useReducer` for deterministic transitions:
- `idle -> optimistic_success -> confirmed` (happy path -- user sees instant success)
- `idle -> optimistic_success -> reverted -> error_with_retry` (failure -- brief success then revert + retry button)
- `idle -> optimistic_success -> pending -> confirmed` (202 path -- success shown throughout)

### Frontend: Error Boundaries — One New Package

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `react-error-boundary` | ^6.1.1 | Catch render crashes in cart/product components | 5.6KB gzipped. The app has zero error boundaries today -- a render crash in CartPanel or ProductDetail kills the entire MiniApp. `resetKeys` prop auto-resets when user retries. |

**Why this over hand-rolled:** Error boundaries require class components. This library provides functional API with `useErrorBoundary()` hook for imperative error throwing from event handlers, plus `resetKeys` for automatic reset.

### Frontend: Revert Toast — No New Package

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| CSS-only inline toast component | N/A | Show "item could not be added" on revert | Do NOT add React Toastify or Sonner for one use case. A 30-line component with CSS `@keyframes` slide-in/fade-out is sufficient. The app already uses CSS animations for cart button states. |

### Backend: Session Pre-Warming — No New Packages

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `VkusVillCart` instance cache | Pure Python dict | Cache initialized cart instances per user | Current code creates `VkusVillCart(cookies_path=...)` per `/api/cart/add` call, potentially running `_warmup_session()` (GET to vkusvill.ru, ~2-3s). Cache the initialized instance keyed by `(telegram_user_id, cookies_mtime)` with 10-min TTL. |
| `httpx.Client` persistent singleton | Already installed | Reuse TCP connections to VkusVill | Current `_request()` creates new client per call, wasting ~200-500ms on TLS handshake. Persistent client with connection pooling eliminates this. |
| FastAPI `lifespan` startup hook | Already installed | Pre-warm sessions on app start | Iterate `data/auth/*/cookies.json` on startup, initialize `VkusVillCart` instances, populate cache. First cart-add is then instant. |

**Session warmup strategy:**
1. **On login**: Always persist `sessid` and `user_id` into cookie JSON (partially done -- `vkusvill_api.py` line 86-94 reads these)
2. **On app startup**: Lifespan event loads all user cookie files, initializes `VkusVillCart` instances into memory cache
3. **On cart-add**: Check cache first. If `sessid`/`user_id` present and mtime unchanged, skip warmup entirely
4. **Background refresh**: Every 30 min, re-validate cached sessions (non-blocking `asyncio.create_task`)

### Backend: Error Classification — No New Packages

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Error type enum in `vkusvill_api.py` | N/A | Classify failures for frontend UX | Return structured `error_type` field so frontend can show appropriate recovery action instead of generic error. |

```python
class CartErrorType:
    TRANSIENT = "transient"       # timeout, 5xx — "tap to retry"
    AUTH_EXPIRED = "auth_expired" # 401, bad session — "re-login needed"
    PRODUCT_GONE = "product_gone" # item unavailable — grey out, no retry
    UNKNOWN = "unknown"           # catch-all — "tap to retry"
```

Frontend maps `error_type` to UX:
- `transient` -> retry button, auto-retry once after 1s
- `auth_expired` -> "Session expired" message with login link
- `product_gone` -> "No longer available", disable add button
- `unknown` -> retry button, manual only

## What NOT to Add

| Technology | Why Not |
|------------|---------|
| Zustand / Jotai / Redux | Cart state is local to App.jsx component tree. `useOptimistic` + `useReducer` is sufficient. |
| TanStack Query / SWR | 3 fetch patterns total. 30KB+ library for cache invalidation the app does not need. |
| `p-retry` / `exponential-backoff` | 5s hard cap means max 1 retry. 20-line utility > library. |
| Sentry / LogRocket | 5-user family app. Console logs + admin diagnostics suffice. |
| Redis / Memcached | Python dict with TTL is sufficient at 5-user scale on 1GB t3.micro. |
| WebSocket for cart updates | SSE + polling already handles updates. Adding WS for cart-only pushes is overengineered. |
| Service Worker for offline retry | Telegram MiniApp WebView has limited SW support. |
| `react-query` for mutations | `useOptimistic` is built into React 19, purpose-built for this. |
| `axios` | `fetch` with `AbortController` already works. Axios adds nothing here. |
| `tenacity` (Python retry) | Simple 2-attempt retry with budget check is 10 lines. Library is overkill. |

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Optimistic UI | `useOptimistic` (React 19 built-in) | Zustand optimistic middleware | Extra dep, React 19 solves natively |
| Error boundaries | `react-error-boundary` ^6.1.1 | Hand-rolled class component | 5.6KB, provides hooks + resetKeys |
| Cart retry | Hand-rolled 20-line utility | `exponential-backoff` npm | 5s budget = max 1 retry, library overkill |
| Session cache | Python dict + mtime check | Redis | 5 users, 1GB RAM, dict sufficient |
| HTTP reuse | Persistent `httpx.Client` | New pool library | httpx has built-in pooling |

## Installation

```bash
# Frontend (in miniapp/)
npm install react-error-boundary@^6.1.1

# Backend -- no new packages needed
```

## Confidence Assessment

| Item | Confidence | Reason |
|------|------------|--------|
| `useOptimistic` in React 19 | HIGH | Shipped in React 19.0 stable, package.json confirms ^19.2.0 |
| `react-error-boundary` React 19 compat | HIGH | v6.x supports React 19 peer dep |
| httpx persistent client perf gain | HIGH | Standard httpx pattern, documented |
| Session warmup eliminates hot-path block | HIGH | `_warmup_session()` code reviewed in vkusvill_api.py |
| Error classification improving UX | MEDIUM | Pattern is standard but VkusVill error responses need empirical validation |
| No need for state management library | HIGH | Verified cart state is local to App.jsx, no cross-component sharing needed |

## Sources

- `miniapp/package.json` -- React 19.2.0 confirmed
- `cart/vkusvill_api.py` -- session warmup, metadata persistence, _request() patterns reviewed
- `miniapp/src/App.jsx` lines 709-1019 -- current cart state machine reviewed
- [React useOptimistic docs](https://react.dev/reference/react/useOptimistic)
- [react-error-boundary npm](https://www.npmjs.com/package/react-error-boundary)
- [httpx Client docs](https://www.python-httpx.org/advanced/clients/)

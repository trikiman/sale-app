# Architecture Research: Instant Cart & Reliability

**Domain:** Optimistic cart UX + session warmup for VkusVill sale monitor
**Researched:** 2026-04-08
**Confidence:** HIGH (based on direct codebase analysis, no external dependencies)

## Current Architecture Snapshot

```
┌─────────────────────────────────────────────────────────────────┐
│                  FRONTEND (React / App.jsx)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ ProductCard   │  │ProductDetail │  │ CartPanel            │  │
│  │ cartStates{}  │  │ cartState    │  │ items[], busyIds     │  │
│  │ cartItemsById │  │ cartItem     │  │ fetchCart()          │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────────────────┘  │
│         │                  │                                     │
│  ┌──────┴──────────────────┴──────────────────────────────────┐ │
│  │ App.jsx state: cartStates, cartItemIds, cartItemsById,     │ │
│  │ cartBusyIds, pendingCartAttemptsRef, cartCount             │ │
│  │ handlers: handleAddToCart, handleSetCartQuantity,           │ │
│  │           pollCartAttemptStatus, refreshCartState           │ │
│  └────────────────────────┬───────────────────────────────────┘ │
└───────────────────────────┼─────────────────────────────────────┘
                            │  fetch /api/cart/*
┌───────────────────────────┼─────────────────────────────────────┐
│              BACKEND (FastAPI / main.py)                         │
│  ┌────────────────────────┴──────────────────────────────────┐  │
│  │ Cart Endpoints                                             │  │
│  │ POST /api/cart/add → cart_add_endpoint (sync, blocking)    │  │
│  │ GET  /api/cart/add-status/{id} → poll pending attempts     │  │
│  │ GET  /api/cart/items/{id} → cart_items_endpoint            │  │
│  │ POST /api/cart/remove, /set-quantity, /clear               │  │
│  ├────────────────────────────────────────────────────────────┤  │
│  │ In-memory: _cart_add_attempts{}, _cart_add_attempt_index{} │  │
│  │ Per-request: VkusVillCart(cookies_path, proxy_manager)     │  │
│  └────────────────────────┬───────────────────────────────────┘  │
└───────────────────────────┼─────────────────────────────────────┘
                            │  httpx POST basket_add.php
┌───────────────────────────┼─────────────────────────────────────┐
│              VkusVillCart (cart/vkusvill_api.py)                 │
│  _ensure_session() → loads cookies → may GET vkusvill.ru        │
│  add() → POST basket_add.php with 1.5s hot-path deadline        │
│  Warmup GET only if sessid/user_id missing from cookie metadata │
└─────────────────────────────────────────────────────────────────┘
```

## Integration Points for v1.13

### 1. Optimistic Cart UI — Where State Lives

**Current state location:** All cart state lives in `App.jsx` as top-level `useState` hooks:
- `cartStates` — per-product button state (`loading`/`pending`/`success`/`error`/null)
- `cartItemIds` — Set of product IDs currently in cart
- `cartItemsById` — Map of product ID to cart item details (quantity, unit, step, etc.)
- `cartBusyIds` — Set of product IDs with in-flight quantity changes
- `pendingCartAttemptsRef` — Map of product ID to pending attempt ID
- `cartCount` — total cart items count

**What changes for optimistic UI:**

The current `handleAddToCart` flow is:
```
tap → setCartStates('loading') → fetch /api/cart/add → wait for response → setCartStates('success'/'error')
```

Optimistic flow should be:
```
tap → immediately setCartStates('success') + add to cartItemIds/cartItemsById + bump cartCount
    → fire-and-forget fetch /api/cart/add
    → on failure: revert cartItemIds/cartItemsById/cartCount + show toast
```

**New vs modified components:**

| Component | Change Type | What Changes |
|-----------|-------------|--------------|
| `App.jsx` `handleAddToCart` | **MODIFY** | Immediately update cartItemIds, cartItemsById, cartCount, cartStates BEFORE fetch. On failure, revert using pre-snapshot. |
| `App.jsx` `handleSetCartQuantity` | **MODIFY** | Same optimistic pattern for quantity changes. |
| `App.jsx` new `revertCartOptimistic()` | **NEW helper** | Accepts snapshot, restores cart state, shows error toast. Reusable by both add and quantity handlers. |
| `ProductCard` | **NO CHANGE** | Already reads cartState/cartItem props — will show success immediately from parent state. |
| `ProductDetail` | **NO CHANGE** | Same — already prop-driven. |
| `CartPanel` | **NO CHANGE** | Opens separately, fetches own state from API. |
| `CartQuantityControl` | **NO CHANGE** | Already prop-driven. |

**Key architectural decision:** Keep optimistic state in `App.jsx` (not a new store/context). The existing prop-drilling pattern works because `ProductCard` and `ProductDetail` already receive `cartState`, `cartItem`, and `isCartBusy` as props. Adding a context or state library would be overengineering for a 5-user family app.

### 2. Session Warmup — Integration with VkusVillCart

**Current problem:** `VkusVillCart._ensure_session()` on every cart operation:
1. Reads cookie file from disk (fast, ~1ms)
2. Builds cookie string (fast)
3. If `sessid` or `user_id` missing from cookie metadata: **GET vkusvill.ru** (slow, 500-2000ms via proxy)

The login flow already saves `sessid` and `user_id` into cookie metadata (line ~2957-2961 in main.py). So the warmup GET only fires when metadata was not captured at login time (race, error, or old cookie files).

**Where warmup should live:**

| Approach | Location | Trigger |
|----------|----------|---------|
| **A: Backend startup warmup** | `main.py` on app startup or first auth check | NEW `@app.on_event("startup")` or lazy on first `/api/auth/status` |
| **B: Eager warmup on auth check** | `main.py` `/api/auth/status/{user_id}` endpoint | MODIFY existing endpoint |
| **C: Dedicated warmup endpoint** | `main.py` NEW `POST /api/cart/warmup` | Frontend calls after auth confirmed |

**Recommendation: Approach B** — Modify `/api/auth/status/{user_id}` to trigger session warmup as a side effect. This endpoint is already called on every page load (App.jsx line ~527). If the cookie file has `sessid` and `user_id` in metadata, warmup is a no-op. If missing, do the warmup GET there (off the cart add hot path).

**Implementation:**

```python
# In /api/auth/status/{user_id} endpoint, after confirming authenticated:
if data.get("authenticated"):
    # Side-effect: ensure session metadata is cached
    cookies_path = _resolve_cart_cookies_path(user_id)
    if os.path.exists(cookies_path):
        with open(cookies_path, 'r') as f:
            cookie_data = json.load(f)
        if isinstance(cookie_data, dict) and (not cookie_data.get('sessid') or not cookie_data.get('user_id')):
            # Warmup: extract sessid/user_id and save back
            background_tasks.add_task(_warmup_session_metadata, user_id, cookies_path)
```

**New backend function:** `_warmup_session_metadata(user_id, cookies_path)` — creates a VkusVillCart, calls `_ensure_session()`, then writes the extracted sessid/user_id back into the cookie file's metadata. Runs as a BackgroundTask so it doesn't block the auth status response.

**New vs modified:**

| Component | Change Type | What Changes |
|-----------|-------------|--------------|
| `backend/main.py` `/api/auth/status` | **MODIFY** | Add BackgroundTask warmup trigger |
| `backend/main.py` `_warmup_session_metadata()` | **NEW function** | Extract and persist session params |
| `cart/vkusvill_api.py` | **NO CHANGE** | `_ensure_session()` already skips GET when metadata present |
| `App.jsx` | **NO CHANGE** | Already calls `/api/auth/status` on load |

### 3. Error Diagnosis — Integration with Existing Contract

**Current failure flow:**
1. Frontend sends `POST /api/cart/add` with `allow_pending: true`
2. Backend creates VkusVillCart, calls `cart.add()` with 1.5s hot-path deadline
3. If VkusVill times out → returns 202 + pending attempt
4. Frontend polls `/api/cart/add-status/{id}` within remaining 5s budget
5. If poll finds item in cart → success; if not found → failure; if budget expires → error

**Where failures happen (to diagnose):**
- `_ensure_session` warmup GET taking too long (session warmup fix addresses this)
- VkusVill `basket_add.php` timing out (1.5s deadline is tight)
- Session expired / cookies stale (need clear error messaging)
- Product out of stock (already handled via POPUP_ANALOGS detection)

**New error recovery integration:**

| Component | Change Type | What Changes |
|-----------|-------------|--------------|
| `App.jsx` `handleAddToCart` | **MODIFY** | After revert from optimistic failure, show actionable retry toast instead of generic error |
| `App.jsx` new `retryCartAdd()` | **NEW helper** | Re-fires same add request, called from toast action |
| `backend/main.py` cart_add_endpoint | **MODIFY** | Return structured error types: `session_expired`, `vkusvill_unavailable`, `sold_out`, `timeout` |
| `cart/vkusvill_api.py` add() | **MODIFY** | Distinguish session errors from API errors in return dict |

### 4. Data Flow: Optimistic Add-to-Cart

```
User taps "В корзину"
    │
    ▼
handleAddToCart(product)
    │
    ├──► IMMEDIATELY: snapshot = {cartItemIds, cartItemsById, cartCount}
    │    setCartItemIds(+pid), setCartItemsById(+placeholder), setCartCount(+1)
    │    setCartStates(pid → 'success')
    │    setToastMessage('Добавлено')
    │    setTimeout(() => setCartStates(pid → null), 2000)
    │
    ├──► ASYNC: fetch('/api/cart/add', { allow_pending: true })
    │    │
    │    ├── 200 success → refreshCartState(1, 3000) to get real qty/price
    │    │
    │    ├── 202 pending → pollCartAttemptStatus (existing flow, unchanged)
    │    │    ├── poll success → refreshCartState
    │    │    └── poll fail → revertCartOptimistic(snapshot) + error toast with retry
    │    │
    │    ├── 400 sold out → revertCartOptimistic(snapshot) + "Раскупили" toast
    │    │
    │    ├── 401 unauthorized → revertCartOptimistic(snapshot) + show login
    │    │
    │    ├── 502/504 unavailable → revertCartOptimistic(snapshot) + retry toast
    │    │
    │    └── AbortError (5s) → revertCartOptimistic(snapshot) + timeout toast with retry
    │
    ▼
revertCartOptimistic(snapshot):
    setCartItemIds(snapshot.cartItemIds)
    setCartItemsById(snapshot.cartItemsById)
    setCartCount(snapshot.cartCount)
    setCartStates(pid → 'error')
    setTimeout(() => setCartStates(pid → null), 2000)
```

### 5. Data Flow: Session Warmup

```
Page Load (App.jsx useEffect)
    │
    ├──► fetch('/api/auth/status/{userId}')
    │         │
    │         ▼
    │    Backend checks cookies exist, UF_USER_AUTH=Y
    │         │
    │         ├── Cookie metadata has sessid + user_id → return immediately
    │         │
    │         └── Missing metadata → spawn BackgroundTask:
    │              _warmup_session_metadata(user_id, cookies_path)
    │                   │
    │                   ├── VkusVillCart._ensure_session()
    │                   │    → GET vkusvill.ru → extract sessid + user_id
    │                   │
    │                   └── Write back to cookies.json metadata
    │                        (next cart add will skip warmup GET)
    │
    ▼
User taps "В корзину" (later)
    │
    ▼
VkusVillCart._ensure_session() → reads cookie file
    → sessid + user_id already in metadata → NO warmup GET needed
    → proceed directly to basket_add.php
```

## Suggested Build Order

Build order is driven by dependencies and value delivery:

### Phase 1: Diagnose Cart Failures
**Why first:** Need to understand what's actually failing before building optimistic UI on top. If the backend can't reliably add to cart, optimistic UI just hides the problem.
- Add structured error types to `cart/vkusvill_api.py` return dicts
- Add error classification to `cart_add_endpoint` responses
- Add diagnostic logging for _ensure_session timing
- **Modifies:** `cart/vkusvill_api.py`, `backend/main.py` cart endpoint
- **No frontend changes**

### Phase 2: Session Warmup
**Why second:** Reduces the most common latency source (warmup GET) before changing UI flow. Makes subsequent optimistic UI more reliable because backend responds faster.
- Add `_warmup_session_metadata()` to backend
- Modify `/api/auth/status` to trigger warmup as BackgroundTask
- **Modifies:** `backend/main.py`
- **No frontend changes**

### Phase 3: Optimistic Cart UX
**Why third:** Now that backend is faster and errors are classified, build the instant UI.
- Add `revertCartOptimistic()` helper to App.jsx
- Modify `handleAddToCart` for immediate state update + async fire
- Handle revert on all failure paths
- **Modifies:** `miniapp/src/App.jsx`
- **No backend changes**

### Phase 4: Error Recovery with Retry
**Why last:** Depends on structured error types (Phase 1) and optimistic revert (Phase 3).
- Add retry action to error toasts
- Add `retryCartAdd()` helper
- Show specific messages per error type (expired session vs unavailable vs sold out)
- **Modifies:** `miniapp/src/App.jsx`
- **No backend changes**

## Anti-Patterns to Avoid

### Anti-Pattern 1: Separate Optimistic State Store

**What people do:** Create a React context or external store (Zustand/Redux) for optimistic cart state.
**Why it's wrong here:** App.jsx already owns all cart state and passes it via props. Adding a separate store creates two sources of truth and sync complexity for a 5-user app.
**Do this instead:** Keep optimistic mutations in the same `useState` hooks. Use a snapshot-and-revert pattern.

### Anti-Pattern 2: Optimistic UI Without Revert

**What people do:** Show success immediately but never revert if the API fails.
**Why it's wrong:** User thinks item is in cart, goes to checkout, item is missing. Trust is destroyed.
**Do this instead:** Always capture pre-mutation snapshot. Always revert on any non-success path. Show clear error message.

### Anti-Pattern 3: Warmup on Every Cart Request

**What people do:** Add a warmup step to every `/api/cart/add` call.
**Why it's wrong:** Doubles latency for every add. The warmup only needs to happen once per session.
**Do this instead:** Warmup once on auth check (page load). Persist to cookie metadata. All subsequent cart ops skip warmup.

### Anti-Pattern 4: Frontend-Side Session Caching

**What people do:** Cache sessid/user_id in frontend localStorage and send it with cart requests.
**Why it's wrong:** sessid is a CSRF token tied to server-side PHP session. Frontend has no business caching it. Backend already handles this via cookie file metadata.
**Do this instead:** Let backend own session state entirely. Frontend just sends user_id and auth headers.

## Sources

- Direct codebase analysis: `cart/vkusvill_api.py`, `backend/main.py`, `miniapp/src/App.jsx`, `miniapp/src/CartPanel.jsx`, `miniapp/src/ProductDetail.jsx`, `miniapp/src/CartQuantityControl.jsx`
- PROJECT.md key decisions: "Metadata-first cart session bootstrap", "Opt-in pending cart add contract", "Pending cart UI is neutral"
- Existing v1.11/v1.12 cart architecture (pending add contract, 5s hard cap, polling)

---
*Architecture research for: v1.13 Instant Cart & Reliability*
*Researched: 2026-04-08*

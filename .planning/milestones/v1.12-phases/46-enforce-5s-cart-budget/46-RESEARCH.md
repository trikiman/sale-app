# Phase 46: Enforce 5s Add-to-Cart Budget - Research

**Researched:** 2026-04-07
**Domain:** Frontend timeout/abort patterns, React state management
**Confidence:** HIGH

## Summary

This is a focused frontend-only change to `miniapp/src/App.jsx`. The current `handleAddToCart` has no fetch timeout and `pollCartAttemptStatus` runs a fixed 20-iteration loop that can take 40+ seconds. The fix adds an AbortController with 5s signal on the initial fetch, and converts the poll loop from iteration-based to time-budget-based.

All decisions are locked by CONTEXT.md. No library additions needed. No backend changes (D5 explicitly keeps TTL at 30s). Single file change.

**Primary recommendation:** Implement AbortController + budget-aware poll loop in App.jsx, touching only `handleAddToCart` and `pollCartAttemptStatus`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- D1: 5s hard cap is frontend-only. Backend stays best-effort.
- D2: AbortController on initial fetch with 5000ms timeout.
- D3: No polling after abort. If fetch takes >4s and returns 202, show "Добавляем в фоне" and stop.
- D4: Budget-aware polling: remainingMs = 5000 - elapsed; poll only while remainingMs > 800; each poll has 1.5s fetch timeout; stop on 404 immediately.
- D5: Backend TTL stays 30s. No backend changes.
- D6: Success after timeout is OK — next cart refresh shows the item.
- D7: Keep all diagnostic logs.

### Claude's Discretion
None specified — all decisions locked.

### Deferred Ideas (OUT OF SCOPE)
- Speeding up `_ensure_session()` / cart init
- Changing VkusVill API interaction patterns
- Background reconciliation improvements
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CART-10 | Tap-to-result within 5s | AbortController 5s on fetch + budget-aware poll loop |
| CART-11 | Frontend enforces 5s hard cap via AbortController | D2: `AbortController` + `setTimeout(abort, 5000)` on `/api/cart/add` fetch |
| CART-12 | Poll uses remaining time budget instead of fixed 20-poll loop | D4: `remainingMs = 5000 - (performance.now() - t0)`, loop while > 800ms |
| CART-13 | Polling stops immediately on 404 | Add explicit 404 check in poll catch block, break loop |
| CART-14 | Backend TTL aligned with frontend budget | D5: TTL stays 30s (already sufficient — no premature pruning within 5s window) |
</phase_requirements>

## Standard Stack

No new libraries needed. This phase uses only browser-native APIs:

| API | Purpose | Why |
|-----|---------|-----|
| `AbortController` | Cancel fetch after 5s | Native browser API, supported in all modern browsers [VERIFIED: MDN Web API] |
| `performance.now()` | Sub-ms timing for budget tracking | Already used in existing diagnostic logs [VERIFIED: codebase] |
| `AbortSignal.timeout()` | Simpler alternative to manual setTimeout+abort | Supported in Chrome 103+, but manual approach from D2 is safer for Telegram WebView [ASSUMED] |

## Architecture Patterns

### Current Flow (broken)
```
tap → fetch /api/cart/add (no timeout, 3.7s avg)
  → 202 pending → poll 20x (700ms + 19×900ms waits + ~5s each fetch)
  → 404 after TTL prune → error at ~41s
```

### Target Flow (D1-D7)
```
tap → fetch /api/cart/add (AbortController 5s)
  → success in <5s → done
  → 202 pending in <3s → budget-poll (remaining time, stop at 800ms left)
  → 202 pending in >4s → "Добавляем в фоне", no poll
  → abort at 5s → error state
  → poll 404 → stop immediately
```

### Key Code Pattern: handleAddToCart with AbortController
```javascript
// Source: D2 from CONTEXT.md + existing code at line 868
const controller = new AbortController()
const timer = setTimeout(() => controller.abort(), 5000)
const t0 = performance.now()
try {
  const res = await fetch('/api/cart/add', {
    method: 'POST',
    signal: controller.signal,
    headers: { ... },
    body: JSON.stringify({ ... })
  })
  clearTimeout(timer)
  // ... handle response
  
  // If 202 pending, check remaining budget
  const elapsed = performance.now() - t0
  if (elapsed > 4000) {
    // D3: not worth polling
    setToastMessage({ text: 'Добавляем в фоне', type: 'info' })
    setCartStates(s => ({ ...s, [pid]: null }))
    return
  }
  void pollCartAttemptStatus(product, data.attempt_id, t0) // pass t0
} catch (err) {
  clearTimeout(timer)
  if (err.name === 'AbortError') {
    // 5s timeout hit
    setCartStates(s => ({ ...s, [pid]: 'error' }))
    setToastMessage({ text: 'Корзина не ответила вовремя', type: 'error' })
  }
}
```

### Key Code Pattern: Budget-aware poll loop
```javascript
// Source: D4 from CONTEXT.md + existing code at line 762
const pollCartAttemptStatus = useCallback(async (product, attemptId, t0) => {
  const pid = String(product.id)
  // ...
  while (true) {
    const remainingMs = 5000 - (performance.now() - t0)
    if (remainingMs < 800) break  // not enough for a round-trip
    
    await wait(Math.min(700, remainingMs - 800))
    
    const pollController = new AbortController()
    const pollTimer = setTimeout(() => pollController.abort(), 
      Math.min(1500, remainingMs - 100))
    
    try {
      const res = await fetch(`/api/cart/add-status/${attemptId}`, {
        signal: pollController.signal,
        headers: getAuthHeaders(userId),
      })
      clearTimeout(pollTimer)
      
      if (res.status === 404) {
        // CART-13: stop immediately on 404
        break
      }
      // ... handle response as before
    } catch (err) {
      clearTimeout(pollTimer)
      if (err.name === 'AbortError') break // budget exhausted
    }
  }
  // ... exhaustion handling
}, [userId])
```

### Anti-Patterns to Avoid
- **Don't use `AbortSignal.timeout(5000)`** — cleaner API but less control over cleanup and Telegram WebView compatibility uncertain [ASSUMED]
- **Don't clear cartStates on background-add** — user should see the button return to normal, not stay in loading

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fetch timeout | Manual XMLHttpRequest timeout | AbortController + setTimeout | Browser-native, works with fetch API [VERIFIED: codebase already uses fetch] |

## Common Pitfalls

### Pitfall 1: Forgetting to clearTimeout on success
**What goes wrong:** AbortController fires after successful response, causing double state update
**How to avoid:** Always `clearTimeout(timer)` in both success and error paths

### Pitfall 2: Race condition between abort and response
**What goes wrong:** Response arrives at ~4999ms, abort fires at 5000ms — both handlers execute
**How to avoid:** Check `controller.signal.aborted` before processing response, or rely on the fact that state updates are idempotent (error overwrites success is acceptable per D6)

### Pitfall 3: pollCartAttemptStatus dependency change
**What goes wrong:** Adding `t0` parameter changes the function signature; `useCallback` deps may need update
**How to avoid:** Pass `t0` as argument (not closure), keep deps array unchanged

### Pitfall 4: Toast message collision
**What goes wrong:** "Добавляем в фоне" toast from D3 overlaps with poll error toast
**How to avoid:** D3 path should NOT start polling, so no collision possible. Just set null cartState.

## Code Examples

### Detecting AbortError
```javascript
// Source: MDN AbortController docs [CITED: developer.mozilla.org/en-US/docs/Web/API/AbortController]
catch (err) {
  if (err.name === 'AbortError') {
    // Timeout — expected
  } else {
    // Network error — unexpected
  }
}
```

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `AbortSignal.timeout()` may not work in Telegram WebView | Standard Stack | LOW — we use manual approach anyway per D2 |
| A2 | State updates from setTimeout race are idempotent | Pitfalls | LOW — error overwriting success is acceptable per D6 |

## Open Questions

None — all decisions are locked and the implementation path is clear.

## Sources

### Primary (HIGH confidence)
- Codebase: `miniapp/src/App.jsx` lines 762-978 — current handleAddToCart and pollCartAttemptStatus
- Codebase: `backend/main.py` line 3016 — `_CART_PENDING_ATTEMPT_TTL_SECONDS = 30.0`
- CONTEXT.md: D1-D7 locked decisions with exact implementation details

### Secondary (MEDIUM confidence)
- MDN AbortController docs — browser API reference [CITED: developer.mozilla.org/en-US/docs/Web/API/AbortController]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries, browser-native APIs only
- Architecture: HIGH — single file change, patterns specified in CONTEXT.md decisions
- Pitfalls: HIGH — straightforward timeout/abort pattern, well-documented

**Research date:** 2026-04-07
**Valid until:** 2026-05-07 (stable browser APIs, no moving targets)

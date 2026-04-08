# Project Research Summary

**Project:** VkusVill Sale Monitor -- v1.13 Instant Cart and Reliability
**Domain:** Optimistic cart UX for e-commerce proxy (Telegram MiniApp to VkusVill API)
**Researched:** 2026-04-08
**Confidence:** HIGH

## Executive Summary

v1.13 is a UX reliability milestone for a 5-user family grocery discount app that proxies cart operations to VkusVill backend. The core problem: cart adds currently take 1-5 seconds with a visible spinner, and frequently fail due to stale session tokens (sessid) blocking the hot path. Every major grocery app (VkusVill native, Instacart, Samokat) shows instant feedback on tap. This milestone closes that gap with optimistic UI, session pre-warming, and structured error recovery.

The recommended approach requires almost zero new dependencies. React 19 useOptimistic is unnecessary for this codebase -- a simpler per-product delta snapshot/rollback pattern in existing useState hooks achieves the same result without architecture changes. The only new package is react-error-boundary (5.6KB). Backend changes are purely structural: session warmup moves off the cart-add hot path into the existing auth-status endpoint as a BackgroundTask, and error responses gain typed classification (transient, auth_expired, product_gone).

The single biggest risk is building optimistic UI on top of a broken backend. Current cart failures are likely caused by stale sessid tokens (VkusVill Bitrix CMS rotates them silently) combined with session warmup GETs blocking the 1.5s hot-path deadline. Diagnosis and fix must come before any frontend optimistic work -- otherwise users see instant success followed by constant rollbacks, which is worse than a spinner.

## Key Findings

### Recommended Stack

Nearly zero new dependencies. React 19.2.0 (already installed) provides the primitives. Backend uses existing FastAPI + httpx with no new packages.

**Core technologies:**
- **React useReducer + snapshot/rollback pattern**: Deterministic cart state transitions -- no external state library needed
- **react-error-boundary ^6.1.1**: Only new package (5.6KB). App has zero error boundaries today
- **Persistent httpx.Client singleton**: Reuse TCP connections, eliminating 200-500ms TLS handshake per request
- **FastAPI BackgroundTask for session warmup**: Pre-extract sessid/user_id on auth check, not on cart add
- **CartErrorType enum in backend**: Structured error classification for frontend UX

**What NOT to add:** Zustand/Redux, TanStack Query, Redis, WebSockets, axios.

### Expected Features

**Must have (table stakes):**
- Diagnose and fix current cart add failures (P0, blocks everything)
- Immediate visual feedback on tap (instant button state change)
- Cart count rollback on failure (per-product delta)
- Clear error messages distinguishing sold-out vs session expired vs VkusVill down
- Retry capability after transient errors

**Should have (differentiators):**
- Optimistic add with background reconciliation
- Session warmup pre-caching (eliminate 1-2s warmup GET on first add)
- Graceful degradation for ambiguous timeouts

**Defer (post-v1.13):**
- Haptic feedback, cart total price preview, undo-add, batch add
- Offline cart queue, automatic retry

### Architecture Approach

All cart state stays in App.jsx existing useState hooks with prop-drilling. No new stores or contexts. The optimistic layer is a ref-based overlay (optimisticAddsRef) tracking per-product deltas, not full cart snapshots. Backend changes are surgical: auth-status endpoint gains a warmup side-effect, cart-add endpoint gains typed error responses.

**Major components modified:**
1. **App.jsx handleAddToCart** -- immediate state update before fetch, background confirmation, per-product rollback
2. **backend/main.py auth-status endpoint** -- triggers session warmup as BackgroundTask
3. **backend/main.py cart-add endpoint** -- returns structured error_type field
4. **cart/vkusvill_api.py** -- error classification, diagnostic timing logs

### Critical Pitfalls

1. **Stale sessid causes silent cart failures** -- Add sessid_saved_at timestamp, treat as stale after 30 min. Likely root cause of current failures.
2. **Optimistic state diverges from real cart** -- Use overlay pattern, never synthetic cartItemsById entries. Reconcile on refreshCartState.
3. **refreshCartState races with optimistic adds** -- Maintain optimisticPending set, merge server state preserving pending entries, generation counter.
4. **Double-add from non-idempotent API** -- Product-scoped cooldown (8-10s), extend backend dedupe to 10s on (user_id, product_id).
5. **Rollback UX whack-a-mole** -- Neutral-pending indicator until confirmed; persistent error with explicit retry button.

## Implications for Roadmap

### Phase 1: Diagnose and Fix Cart Failures
**Rationale:** Must understand what is actually failing before building optimistic UI on top.
**Delivers:** Reliable cart-add backend with structured error types; diagnostic logging.
**Addresses:** P0 table-stakes feature (diagnose failures), error classification.
**Avoids:** Stale sessid pitfall, warmup blocking hot path.
**Modifies:** cart/vkusvill_api.py, backend/main.py. No frontend changes.

### Phase 2: Session Warmup Optimization
**Rationale:** Reduces most common latency source before changing UI flow.
**Delivers:** Sub-50ms _ensure_session when cached; sessid auto-refresh every 15-30 min.
**Addresses:** Session warmup pre-caching; first-add latency from 3-4s to under 1s.
**Avoids:** Warmup on hot path, cookie file races.
**Modifies:** backend/main.py auth-status endpoint. No frontend changes.

### Phase 3: Optimistic Cart UX
**Rationale:** Backend is now fast and reliable; optimistic reverts will be rare.
**Delivers:** Instant visual feedback, background confirmation, per-product delta rollback.
**Addresses:** Immediate feedback, optimistic add, cart count accuracy.
**Avoids:** State divergence, double-add, refresh race, rollback UX issues.
**Modifies:** miniapp/src/App.jsx. No backend changes.

### Phase 4: Error Recovery and Polish
**Rationale:** Depends on error types (Phase 1) and optimistic revert (Phase 3).
**Delivers:** Actionable retry toasts, react-error-boundary, auto-retry for transient errors.
**Addresses:** Clear error messages, error recovery UX.
**Modifies:** miniapp/src/App.jsx. No backend changes.

### Phase Ordering Rationale

- Phase 1 before 2: Must know what fails before optimizing warmup
- Phase 2 before 3: Backend must be reliable so optimistic reverts are rare
- Phase 3 before 4: Core optimistic flow before retry/recovery polish
- All 4 phases modify different files with minimal overlap

### Research Flags

Phases needing deeper research during planning:
- **Phase 1:** Needs production log analysis for sessid staleness hypothesis. VkusVill API experimentation for exact sessid TTL.
- **Phase 3:** Per-product delta rollback + refreshCartState merge is the most complex piece.

Standard patterns (skip research-phase):
- **Phase 2:** BackgroundTask warmup is straightforward FastAPI pattern.
- **Phase 4:** Error boundary and toast UX are standard React patterns.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Nearly zero new deps; React 19 already installed |
| Features | HIGH | Well-established e-commerce optimistic UI patterns |
| Architecture | HIGH | Based on direct codebase analysis |
| Pitfalls | HIGH | Grounded in specific code paths and line numbers |

**Overall confidence:** HIGH

### Gaps to Address

- **VkusVill sessid TTL**: Exact rotation interval unknown. Assumed 30 min. Needs empirical validation in Phase 1.
- **VkusVill error response format**: Not fully cataloged. Phase 1 diagnostic logging will fill this gap.
- **useOptimistic vs manual pattern**: Resolution: use manual snapshot/rollback -- equivalent behavior, no architecture changes.

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis: cart/vkusvill_api.py, backend/main.py, miniapp/src/App.jsx
- miniapp/package.json -- React 19.2.0 confirmed
- PROJECT.md key decisions table

### Secondary (MEDIUM confidence)
- React useOptimistic docs, react-error-boundary npm, httpx Client docs
- Optimistic UI patterns (OpenReplay, LogRocket, freeCodeCamp)

### Tertiary (LOW confidence)
- VkusVill Bitrix CMS sessid rotation -- inferred from Bitrix defaults

---
*Research completed: 2026-04-08*
*Ready for roadmap: yes*

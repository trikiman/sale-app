# Requirements: VkusVill Sale Monitor

**Defined:** 2026-04-08
**Core Value:** Family members see every VkusVill discount and can add to cart in one tap

## v1.13 Requirements

Requirements for Instant Cart & Reliability milestone. Each maps to roadmap phases.

### Cart Reliability

- [ ] **CART-15**: User's add-to-cart succeeds reliably instead of showing spinner then error
- [ ] **CART-16**: Backend logs expose clear root cause for current cart failures (expired session, proxy issue, VkusVill API change)

### Performance

- [ ] **PERF-01**: Session sessid/user_id are pre-cached on app load so first cart add doesn't block on warmup GET
- [ ] **PERF-02**: Cart add hot path completes in under 5 seconds end-to-end including API response

### Optimistic UX

- [ ] **UX-20**: User sees instant success feedback (checkmark + cart count update) on tap, before API response
- [ ] **UX-21**: If background API call fails, optimistic state reverts and user sees brief error toast
- [ ] **UX-22**: Button returns to tappable state within 2 seconds after revert

### Error Recovery

- [ ] **ERR-01**: User sees distinct error messages for sold-out, session-expired, VkusVill-down, and network-error states
- [ ] **ERR-02**: Session-expired errors prompt re-login instead of showing cart error

## Future Requirements

### Deferred from v1.13

- **UX-23**: Cart count badge updates optimistically on tap (selected but bundled into UX-20)
- **ERR-03**: Gentle revert + toast on optimistic failure (bundled into UX-21)
- **HAPTIC-01**: Haptic feedback on add-to-cart tap
- **BATCH-01**: Batch add multiple items at once

## Out of Scope

| Feature | Reason |
|---------|--------|
| Offline cart queue | VkusVill cart is server-authoritative; Telegram MiniApp has no ServiceWorker |
| Automatic retry on failure | VkusVill bans concurrent connections; retries risk rate limits |
| Speculative pre-add | Absurd for grocery discount aggregator; wastes VkusVill session budget |
| Real-time cart sync via WebSocket | Overkill for 5-user family app; SSE + polling sufficient |
| React 19 useOptimistic migration | Manual snapshot+rollback is simpler and avoids framework migration |
| Persistent pending state across restarts | 5s hard cap makes pending states transient by design |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CART-15 | — | Pending |
| CART-16 | — | Pending |
| PERF-01 | — | Pending |
| PERF-02 | — | Pending |
| UX-20 | — | Pending |
| UX-21 | — | Pending |
| UX-22 | — | Pending |
| ERR-01 | — | Pending |
| ERR-02 | — | Pending |

**Coverage:**
- v1.13 requirements: 9 total
- Mapped to phases: 0
- Unmapped: 9 ⚠️

---
*Requirements defined: 2026-04-08*
*Last updated: 2026-04-08 after initial definition*

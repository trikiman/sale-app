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
- [ ] **PERF-02**: Cart add completes with real VkusVill API confirmation in under 5 seconds end-to-end

### Error Recovery

- [ ] **ERR-01**: User sees distinct error messages for sold-out, session-expired, VkusVill-down, and network-error states
- [ ] **ERR-02**: Session-expired errors prompt re-login instead of showing cart error

## Future Requirements

### Deferred from v1.13

- **UX-20**: Optimistic cart UX — deferred, user wants real API confirmation not fake instant success
- **HAPTIC-01**: Haptic feedback on add-to-cart tap
- **BATCH-01**: Batch add multiple items at once

## Out of Scope

| Feature | Reason |
|---------|--------|
| Optimistic cart UI | User wants real API confirmation, not fake instant success |
| Offline cart queue | VkusVill cart is server-authoritative; Telegram MiniApp has no ServiceWorker |
| Automatic retry on failure | VkusVill bans concurrent connections; retries risk rate limits |
| Speculative pre-add | Absurd for grocery discount aggregator; wastes VkusVill session budget |
| Real-time cart sync via WebSocket | Overkill for 5-user family app; SSE + polling sufficient |
| Persistent pending state across restarts | 5s hard cap makes pending states transient by design |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CART-15 | Phase 47 | Pending |
| CART-16 | Phase 47 | Pending |
| PERF-01 | Phase 48 | Pending |
| PERF-02 | Phase 48 | Pending |
| ERR-01 | Phase 49 | Pending |
| ERR-02 | Phase 49 | Pending |

**Coverage:**
- v1.13 requirements: 6 total
- Mapped to phases: 6
- Unmapped: 0

---
*Requirements defined: 2026-04-08*
*Last updated: 2026-04-08 after roadmap creation*

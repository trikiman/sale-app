# Requirements — v1.13 Instant Cart & Reliability

## Milestone Goal

Make add-to-cart feel instant with optimistic UI and fix current failures so cart adds actually succeed.

## Requirements

### Cart Reliability (Phase 47)

- [x] **CART-15**: Cart-add endpoint returns structured error_type field (auth_expired, product_gone, transient, timeout) instead of generic 500
- [x] **CART-16**: Backend logs show specific root cause for every cart-add failure with diagnostic context

### Performance (Phase 48)

- [x] **PERF-01**: On login, sessid and user_id are pre-extracted and cached so no warmup GET blocks the first cart add
- [x] **PERF-02**: Stale sessid (older than 30 min) is auto-refreshed before it causes a cart failure

### Error Recovery (Phase 49)

- [x] **ERR-01**: User sees distinct messages for sold-out, session-expired, VkusVill-down, and network-error states
- [x] **ERR-02**: After a transient error, user can retry the add without refreshing the page (🔄 retry state)

### Cart Optimistic State (Phase 51)

- [x] **CART-17**: Quantity stepper appears on product card after successful cart-add (optimistic state not overwritten by fallback)
- [x] **CART-18**: refreshCartState preserves optimistic cart items when backend returns source_unavailable fallback

### Non-Goals

- No changes to VkusVill API interaction protocol
- No background reconciliation changes

## Traceability

| REQ | Phase | Status |
|-----|-------|--------|
| CART-15 | 47 | Satisfied |
| CART-16 | 47 | Satisfied |
| PERF-01 | 48 | Satisfied |
| PERF-02 | 48 | Satisfied |
| ERR-01 | 49 | Satisfied |
| ERR-02 | 49 | Satisfied |
| CART-17 | 51 | Satisfied |
| CART-18 | 51 | Satisfied |

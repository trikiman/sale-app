# Requirements: VkusVill Sale Monitor

**Defined:** 2026-04-01
**Core Value:** Family members see every VkusVill discount and can add to cart in one tap

## v1.4 Requirements

Requirements for Proxy Centralization milestone. Each maps to roadmap phases.

### Image Proxy

- [ ] **IMG-01**: `/api/img` endpoint uses ProxyManager rotation instead of `SOCKS_PROXY` env var
- [ ] **IMG-02**: Detail gallery images route through `/api/img` backend proxy (not loaded directly by browser)

### Cart API

- [ ] **CART-04**: Cart API (`vkusvill_api.py`) uses ProxyManager for VkusVill API calls

### Login

- [ ] **LOGIN-01**: Login flow uses ProxyManager for Chrome `--proxy-server` flag

### Product Detail

- [ ] **DETAIL-01**: Product detail HTML fetch uses ProxyManager as primary (not fallback)

### Infrastructure

- [ ] **INFRA-01**: ProxyManager is the single gateway abstraction — new VkusVill-facing code uses it by default

## Future Requirements

Deferred. Tracked but not in current roadmap.

### Proxy Pool Scaling

- **POOL-01**: Add multiple proxy sources (not just proxifly)
- **POOL-02**: More aggressive refresh scheduling
- **POOL-03**: Paid proxy provider as fallback option

## Out of Scope

| Feature | Reason |
|---------|--------|
| Proxy pool scaling | 8 IPs sufficient for 5-user family app, handle separately if needed |
| Switching proxy providers | Current free proxifly source works, optimize later |
| HTTPS proxy support | SOCKS5 covers all current needs |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| IMG-01 | TBD | Pending |
| IMG-02 | TBD | Pending |
| CART-04 | TBD | Pending |
| LOGIN-01 | TBD | Pending |
| DETAIL-01 | TBD | Pending |
| INFRA-01 | TBD | Pending |

**Coverage:**
- v1.4 requirements: 6 total
- Mapped to phases: 0
- Unmapped: 6 ⚠️

---
*Requirements defined: 2026-04-01*
*Last updated: 2026-04-01 after initial definition*

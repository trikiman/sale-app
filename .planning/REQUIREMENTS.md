# Requirements: VkusVill Sale Monitor — Testing & QA Milestone

**Defined:** 2026-03-31
**Core Value:** Prevent regressions and ensure every feature works as expected

## v1.1 Requirements

### Browser E2E Testing

- [ ] **TEST-01**: Browser E2E test verifies product grid loads with green/red/yellow items and images
- [ ] **TEST-02**: Browser E2E test verifies category filter shows/hides products correctly
- [ ] **TEST-03**: Browser E2E test verifies product detail drawer opens with price, image, and description
- [ ] **TEST-04**: Browser E2E test verifies cart add button works and shows feedback (spinner → checkmark)
- [ ] **TEST-05**: Browser E2E test verifies favorites toggle (heart icon) works
- [ ] **TEST-06**: Browser E2E test verifies theme toggle switches between dark and light mode
- [ ] **TEST-07**: Browser E2E test verifies search/filter by product name works

### API Unit Testing

- [ ] **TEST-08**: Pytest covers /api/products endpoint (returns products with correct schema)
- [ ] **TEST-09**: Pytest covers /api/cart endpoints (add, remove, list — auth required)
- [ ] **TEST-10**: Pytest covers /api/favorites endpoints (add, remove, list — auth required)
- [ ] **TEST-11**: Pytest covers admin endpoints (scraper triggers, status — admin token required)
- [ ] **TEST-12**: Pytest covers auth flow (login state, session validation)

### Scraper Verification

- [ ] **TEST-13**: Automated verification script confirms green scraper accuracy ≥90% vs live site
- [ ] **TEST-14**: Automated verification confirms red/yellow scraper output matches expected schema
- [ ] **TEST-15**: Automated verification confirms no phantom items (products not on live site)

## Future Requirements

Deferred to next milestone:
- **FEAT-01**: Price history page
- **POL-01**: Cookie expiry detection and re-login prompt
- **POL-02**: Test file cleanup

## Out of Scope

| Feature | Reason |
|---------|--------|
| Load/stress testing | Family app, 5 users max |
| CI/CD pipeline setup | Manual deploy works fine for family scale |
| Mobile-specific testing | Telegram MiniApp handles mobile, desktop browser sufficient |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| TEST-01 | Phase 10 | Pending |
| TEST-02 | Phase 10 | Pending |
| TEST-03 | Phase 10 | Pending |
| TEST-04 | Phase 10 | Pending |
| TEST-05 | Phase 10 | Pending |
| TEST-06 | Phase 10 | Pending |
| TEST-07 | Phase 10 | Pending |
| TEST-08 | Phase 11 | Pending |
| TEST-09 | Phase 11 | Pending |
| TEST-10 | Phase 11 | Pending |
| TEST-11 | Phase 11 | Pending |
| TEST-12 | Phase 11 | Pending |
| TEST-13 | Phase 12 | Pending |
| TEST-14 | Phase 12 | Pending |
| TEST-15 | Phase 12 | Pending |

**Coverage:**
- v1.1 requirements: 15 total
- Mapped to phases: 15
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-31*

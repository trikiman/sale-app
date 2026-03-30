# Requirements: VkusVill Sale Monitor — Bug Fix Milestone

**Defined:** 2026-03-30
**Core Value:** Family members see every VkusVill discount and can add to cart in one tap

## v1 Requirements

Requirements for this bug fix milestone. Each maps to roadmap phases.

### Security

- [x] **SEC-06**: Favorites endpoints validate user identity via Telegram initData HMAC or X-Telegram-User-Id header match (BUG-038)
- [x] **SEC-07**: Cart endpoints validate user identity via Telegram initData HMAC or X-Telegram-User-Id header match (BUG-039)
- [ ] **SEC-08**: Frontend sends Telegram initData in Authorization header when running as MiniApp

### Scraper Accuracy

- [ ] **SCRP-07**: Green scraper captures ≥90% of items shown on live VkusVill green section (BUG-067)
- [ ] **SCRP-08**: Stock data shows real quantity, not placeholder 99, for all green products (BUG-068)
- [ ] **SCRP-09**: Category scraper assigns categories deterministically (first-write-wins within a run) (BUG-053)

### Telegram Bot

- [ ] **BOT-04**: Notifications for new products sent to ALL users with matching favorites, not just the first (BUG-044)
- [ ] **BOT-05**: Category matching uses exact category name, not fuzzy substring (BUG-056)

### Frontend UX

- [ ] **UX-06**: Light mode theme correctly applies all CSS variables — no hardcoded dark colors remain (UX-01)
- [ ] **UX-07**: Product list uses composite keys (id-type) — no duplicate key warnings in console (UX-02)
- [ ] **UX-08**: Cart items with quantity 0 are automatically filtered from display (UX-03)
- [ ] **UX-09**: Scraper trigger button recovers from 403 error — shows error state, not infinite spinner (UX-04)
- [ ] **UX-10**: Empty state message delayed until AnimatePresence exit completes (UX-05)

### Backend Logic

- [ ] **BACK-01**: "Run All" scrapers queues merge task after all 3 scrapers complete (BUG-046)

## v2 Requirements

Deferred to future milestone. Tracked but not in current roadmap.

### Polish
- **POL-01**: Cookie expiry detection and re-login prompt
- **POL-02**: Test file cleanup (remove test_*.py)
- **POL-03**: Improved logging and monitoring dashboard

### Features
- **FEAT-01**: Price history page (design doc exists in docs/memory/plans/historypage.md)
- **FEAT-02**: "Открыть" web app button in Telegram notifications
- **FEAT-03**: Admin panel remote access improvements

## Out of Scope

| Feature | Reason |
|---------|--------|
| Docker containerization | systemd works fine, not needed for single-server family app |
| HTTPS/domain setup | Vercel handles HTTPS already |
| Cookie encryption at rest | Low risk for family-only app, adds complexity |
| OAuth login | VkusVill only supports phone+SMS |
| Mobile native app | Telegram MiniApp IS the mobile experience |
| Category scraper eviction of old products | Nice-to-have, not a bug — defer to polish milestone |
| Database schema migration to ORM | Works fine as-is, risk of regression |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SEC-06 | Phase 1 | Complete |
| SEC-07 | Phase 1 | Complete |
| SEC-08 | Phase 1 | Pending |
| SCRP-07 | Phase 2 | Pending |
| SCRP-08 | Phase 2 | Pending |
| SCRP-09 | Phase 3 | Pending |
| BOT-04 | Phase 4 | Pending |
| BOT-05 | Phase 4 | Pending |
| UX-06 | Phase 5 | Pending |
| UX-07 | Phase 5 | Pending |
| UX-08 | Phase 5 | Pending |
| UX-09 | Phase 5 | Pending |
| UX-10 | Phase 5 | Pending |
| BACK-01 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 14 total
- Mapped to phases: 14
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-30*
*Last updated: 2026-03-30 after initial definition*

# Requirements: v1.11 Cart Responsiveness & Truth Recovery

**Status:** Planned
**Created:** 2026-04-06
**Goal:** Make add-to-cart feel fast and trustworthy by enforcing a hard 5-second user wait budget and reconciling ambiguous cart outcomes in the background.

## Add-to-Cart Response Budget

- [ ] **CART-04**: User gets a final add result or explicit pending state within 5.0 seconds of tapping add to cart.
- [ ] **UI-19**: User sees a short non-blocking "checking cart" message when the add result is still uncertain after the 5-second budget is exhausted.
- [ ] **CART-05**: User can keep browsing and using the MiniApp while cart reconciliation continues in the background.

## Cart Truth Recovery

- [ ] **CART-06**: User eventually sees the correct cart state after a slow or timed-out add that may have succeeded late upstream.
- [ ] **CART-07**: User does not see a hard failure or sold-out removal when cart truth is still ambiguous.
- [ ] **CART-08**: User does not create duplicate add attempts by tapping repeatedly while one add is still unresolved.
- [ ] **CART-09**: User is not blocked by backend session repair or follow-up cart reads once the 5-second response budget is exhausted.

## Operations & Verification

- [ ] **OPS-04**: Team can inspect cart-add latency, timeout reason, and reconciliation outcome for slow cart actions.
- [ ] **QA-04**: Automated coverage protects the 5-second add UX budget and eventual cart-truth recovery flow.

## Future Requirements

- [ ] **CART-10**: User receives live cart-outcome updates across tabs or sessions if background reconciliation later needs to surface outside the current page.
- [ ] **OPS-05**: Team has historical latency percentiles and trend dashboards for cart add and cart read behavior instead of relying only on per-request logs.

## Out of Scope

- Replacing the current VkusVill cart integration with a fully reverse-engineered private API in this milestone.
- Redesigning the full cart panel or product-card layout beyond the feedback needed for the bounded add flow.
- Guaranteeing that VkusVill itself completes every cart add within 5 seconds; this milestone caps the visible user wait path instead.

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CART-04 | — | Pending |
| UI-19 | — | Pending |
| CART-05 | — | Pending |
| CART-06 | — | Pending |
| CART-07 | — | Pending |
| CART-08 | — | Pending |
| CART-09 | — | Pending |
| OPS-04 | — | Pending |
| QA-04 | — | Pending |

**Coverage:**
- v1 requirements: 9 total
- Mapped to phases: 0
- Unmapped: 9

---
*Requirements defined: 2026-04-06*
*Last updated: 2026-04-06 after initial definition*

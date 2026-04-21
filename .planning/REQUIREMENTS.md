# Requirements — v1.14 Cart Truth & History Semantics

## Milestone Goal

Make add-to-cart work in real user flows and make history/restock semantics reflect real sale transitions instead of fake reentries.

## Requirements

### Cart Truth

- [x] **CART-19**: User can tap add-to-cart in the MiniApp and the selected product actually appears in the user's real VkusVill cart
- [x] **CART-20**: Cart UI only transitions into success/quantity-control state when backend truth confirms the item is in cart or the add succeeded definitively
- [x] **CART-21**: When cart add is ambiguous or fails, the user sees a truthful stable state and can retry or recover without reloading the app manually

### History Semantics

- [x] **HIST-09**: Sale history does not create fake restocks or fake session reentries from stale scrape gaps, merge artifacts, or continuity heuristics
- [x] **HIST-10**: History UI and notifier semantics distinguish continued sale, first appearance, and true return-to-sale events using the corrected session model
- [x] **HIST-11**: Existing persisted history/session data is repaired or rebuilt so current user-visible history no longer contains already-recorded fake restocks or fake reentries

### Observability & Verification

- [x] **OPS-05**: Admin/status surfaces and logs expose enough evidence to explain why a cart attempt or sale-session transition received its classification
- [x] **QA-05**: Milestone verification includes live cart-add proof and history-semantic checks against fresh production-like data

## v2 Requirements

### Future Follow-Ups

- **CART-22**: Users can self-diagnose cart failures from end-user-visible diagnostics without opening admin/operator tools
- **HIST-12**: History detail explains exactly which source transitions caused a session to close or reopen

## Out of Scope

| Feature | Reason |
|---------|--------|
| New auth system or non-VkusVill checkout flow | Not related to the user-reported failures |
| Replacing the current stack or deployment model | Existing Python + React + EC2/Vercel setup is sufficient for this milestone |
| New discovery/search features | The priority is fixing cart truth and session semantics first |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| OPS-05 | Phase 52 | Complete |
| CART-19 | Phase 53 | Complete |
| CART-20 | Phase 53 | Complete |
| CART-21 | Phase 53 | Complete |
| HIST-09 | Phase 54 | Complete |
| HIST-10 | Phase 54 | Complete |
| HIST-11 | Phase 54 | Complete |
| QA-05 | Phase 55 | Complete |

**Coverage:**
- v1 requirements: 8 total
- Mapped to phases: 8
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-21*
*Last updated: 2026-04-21 after completing phases 52-55*

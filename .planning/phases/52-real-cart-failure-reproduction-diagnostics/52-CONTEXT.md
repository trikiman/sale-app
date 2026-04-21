# Phase 52: Real Cart Failure Reproduction & Diagnostics - Context

**Gathered:** 2026-04-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Reproduce the real MiniApp cart failure with concrete backend and upstream evidence so the next fixes are based on observed behavior, not inferred code paths.

</domain>

<decisions>
## Implementation Decisions

### Reproduction Surface
- Use the live Vercel/EC2 deployment and authenticated guest flow as the source of truth
- Treat `/api/cart/items`, `/api/cart/add`, backend journals, and direct VkusVill AJAX calls as the evidence set

### Failure Hypothesis
- The broken user experience is caused by cart truth timing and transport behavior, not by a dead frontend shell
- Stale session refresh and transport choice must be measured separately from upstream basket_add success

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `cart/vkusvill_api.py` contains all cart transport/session logic
- `backend/main.py` exposes `/api/cart/add`, `/api/cart/add-status`, and `/api/cart/items`
- `database/sale_history.py` owns sale session truth and repairable history state

### Established Patterns
- Backend emits structured cart attempt logs and typed `error_type` responses
- History integrity is verified through focused pytest suites under `backend/`

### Integration Points
- Cart UI trusts `/api/cart/items` and `/api/cart/add-status`
- History UI and notifier trust `sale_sessions` and `product_catalog` statistics

</code_context>

<specifics>
## Specific Ideas

- Capture one direct upstream cart add/remove with the real auth cookies
- Compare backend cart behavior with direct upstream behavior
- Query the production `sale_sessions` table for suspicious short-gap reentries

</specifics>

<deferred>
## Deferred Ideas

- Broader auth redesign
- New user-facing diagnostics UI

</deferred>

# Phase 44: Frontend Bounded Add UX - Context

**Gathered:** 2026-04-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Cap the visible add-to-cart interaction at 5 seconds, consume the new backend pending contract, and replace the plain add button with an in-cart quantity control once the product is effectively in the cart. This phase covers the card/detail/cart-control behavior, pending/failure treatment, and cross-surface syncing for the same product. It does not add new backend cart semantics beyond what Phase 43 already shipped, and it does not cover diagnostics/release verification work from Phase 45.

</domain>

<decisions>
## Implementation Decisions

### Pending-State Behavior
- **D-01:** When the backend returns `pending`, stop the visible loading spinner quickly and switch into a neutral **"checking cart"** state instead of showing a red error state.
- **D-02:** Keep the rest of the MiniApp usable while reconciliation continues. Only the control for the affected product should be temporarily locked.
- **D-03:** Do not show full success while the add is still ambiguous. Wait for confirmation, then switch into the in-cart quantity control.
- **D-04:** If reconciliation later confirms failure, return to the normal add button state instead of leaving a stuck pending control.

### Quantity Control Shape
- **D-05:** After confirmed success, replace the plain add button with a **VkusVill-like pill quantity control** rather than switching back to the cart icon.
- **D-06:** Use the same overall control pattern on the product card and in the detail drawer, with a compact version on cards and a slightly larger version in detail.
- **D-07:** All visible copies of the same product must stay in sync. If one surface switches into the in-cart control, the same product on other visible surfaces should stop showing the plain add button too.

### Quantity Input Rules
- **D-08:** For `шт` items, quantity entry is whole-number only and `+` / `-` step by `1`.
- **D-09:** For weighted items, typed decimal entry is allowed (example: `0.73 кг`).
- **D-10:** Accept both comma and dot as decimal input and normalize to one displayed format in the UI.
- **D-11:** For weighted `+` / `-`, use the product’s natural backend/cart step if it can be derived; otherwise the planner/executor may choose the safest fallback step.

### Removal And Failure Behavior
- **D-12:** Quantity `0` means remove the item from cart.
- **D-13:** Pending timeout must not be treated like sold-out. Sold-out/removal UI should only happen after a confirmed sold-out result.
- **D-14:** Confirmed failure returns to the normal add button with a short retryable error, not a persistent red state.
- **D-15:** If a product is already effectively in cart, repeated user interaction should keep/sync the quantity control rather than registering another add flow.

### the agent's Discretion
- Exact wording, iconography, and animation for the neutral "checking cart" state, as long as it is visibly distinct from both success and failure.
- Exact compact vs expanded sizing details for the card and detail-drawer quantity controls.
- Exact local state model for syncing the same product across card, detail drawer, and cart count surfaces.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope & Milestone Contract
- `.planning/ROADMAP.md` — Phase 44 goal, requirements mapping, and success criteria.
- `.planning/REQUIREMENTS.md` — `CART-04`, `UI-19`, `CART-05`, `CART-07`, and `CART-08` define the frontend contract for bounded cart UX.
- `.planning/PROJECT.md` — Current milestone framing for cart responsiveness and truth recovery.
- `.planning/STATE.md` — Current position and next-step routing for Phase 44.

### Prior Cart Contract Decisions
- `.planning/phases/43-backend-cart-response-contract/43-CONTEXT.md` — Backend pending contract, dedupe assumptions, and opt-in add-status flow that this frontend phase must consume.
- `backend/main.py` — Current `/api/cart/add` and `/api/cart/add-status/{attempt_id}` contract implemented in Phase 43.
- `cart/vkusvill_api.py` — Bounded cart add behavior and timeout semantics the frontend now sits on top of.

### Current Frontend Cart UI
- `miniapp/src/App.jsx` — Main product-card cart button state machine, cart count/item tracking, and the current inline timeout reconciliation path that needs replacing.
- `miniapp/src/ProductDetail.jsx` — Detail drawer cart button and secondary add surface that must stay in sync with the main card.
- `miniapp/src/CartPanel.jsx` — Existing quantity controls, remove behavior, and quantity adjustment patterns that can be reused or adapted.
- `miniapp/src/index.css` — Current cart button, detail button, and cart-panel quantity control styling primitives.
- `miniapp/src/productMeta.js` — Existing unit/weight formatting helpers that influence `шт` vs `кг` presentation.

### Prior Frontend Constraints
- `.planning/phases/41-main-screen-card-performance/41-CONTEXT.md` — Keep current main card UI mostly intact and preserve cart/detail behavior unless the new contract requires a targeted change.
- `.planning/codebase/ARCHITECTURE.md` — Frontend/backend/cart flow and where state lives today.
- `.planning/codebase/CONVENTIONS.md` — Existing frontend naming and React conventions used in `miniapp/src`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `miniapp/src/CartPanel.jsx` already has plus/minus quantity controls, busy states, and remove-at-zero behavior that can be adapted for the in-card control.
- `miniapp/src/App.jsx` already tracks `cartCount`, `cartItemIds`, and per-product `cartStates`, so Phase 44 can build on an existing cart-state layer instead of starting from scratch.
- `miniapp/src/productMeta.js` already distinguishes `шт` and weighted units and provides formatting helpers relevant to the visible quantity text.

### Established Patterns
- The current product card uses a temporary `loading/success/error/null` button state machine.
- The current timeout path still calls `refreshCartState(3, 1200)` inline after abort, which is the visible wait Phase 44 must remove.
- The detail drawer and main card already share the same `handleAddToCart` callback and `cartState`, so a unified state model is feasible.
- The app already uses toasts/banners for feedback rather than modal alerts.

### Integration Points
- `miniapp/src/App.jsx` is the primary integration point for switching from legacy timeout behavior to the new `allow_pending` + add-status flow.
- `miniapp/src/ProductDetail.jsx` must consume the same in-cart control state so it does not drift from the main card.
- `miniapp/src/CartPanel.jsx` contains the closest existing quantity-control behavior and should inform the new card/detail control instead of inventing a separate interaction model.

</code_context>

<specifics>
## Specific Ideas

- The desired post-success control is explicitly inspired by VkusVill’s own card/cart widget.
- Weighted items should allow direct decimal entry like `0.73 кг`.
- Count-based items should allow direct integer entry like `2 шт`.
- The same product should not show a plain add button on one surface and a quantity control on another once it is effectively in cart.

</specifics>

<deferred>
## Deferred Ideas

### Reviewed Todos (not folded)
- `2026-04-02-history-search-shows-all-matching-products-from-catalog.md` — surfaced on generic MiniApp keywords only; unrelated to cart UX, keep deferred.
- `2026-04-06-clarify-stale-banner-freshness-vs-updated-time.md` — valid UI issue, but separate from the bounded add/cart-control scope of Phase 44.

</deferred>

---

*Phase: 44-frontend-bounded-add-ux*
*Context gathered: 2026-04-06*

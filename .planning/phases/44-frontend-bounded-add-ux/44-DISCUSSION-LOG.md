# Phase 44: Frontend Bounded Add UX - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-06
**Phase:** 44-frontend-bounded-add-ux
**Areas discussed:** pending-state behavior, quantity control shape, quantity input rules, removal and failure behavior

---

## Pending-state behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Keep blocking spinner | Spinner stays until cart truth is known. | |
| Neutral checking state | Stop spinner fast, show a non-error "checking cart" state, keep only that product control locked. | ✓ |
| Treat pending as error | Timeout/pending becomes a red retry state immediately. | |

**User's choice:** Use the neutral checking state.
**Notes:** User accepted the recommendation that pending should not look like failure and should not freeze the rest of the app.

---

## Quantity control shape

| Option | Description | Selected |
|--------|-------------|----------|
| Return to plain cart icon | Show a short success flash, then go back to the add button. | |
| VkusVill-like in-cart pill | After success, switch to a `- amount +` style control inspired by VkusVill. | ✓ |
| Other custom control | Invent a different persistent in-cart control pattern. | |

**User's choice:** Use the VkusVill-like pill control.
**Notes:** User explicitly wants the control to stay on the card after success instead of reverting to the plain button, and wants visible copies of the same product to sync across surfaces.

---

## Quantity input rules

| Option | Description | Selected |
|--------|-------------|----------|
| Button-only quantity changes | Only `+` / `-`, no direct typing. | |
| Typed `шт` and `кг` entry | Allow direct numeric entry for count items and weighted items, with `+/-` still available. | ✓ |
| Detail-only typing | Only the detail drawer allows typed quantity input. | |

**User's choice:** Allow typed entry for both `шт` and `кг`.
**Notes:** User gave concrete examples: weighted items like `0.73 кг` and count items like `2 шт`. Recommended defaults also keep integer-only behavior for `шт` and decimal input for weighted items.

---

## Removal and failure behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Pending behaves like sold-out/error | Ambiguous timeout can immediately flip into failure visuals. | |
| Confirmed-only failure treatment | Quantity `0` removes, pending never marks sold-out, and real failure returns to the normal add button with retry. | ✓ |
| Persistent red error state | Leave the control red until the user manually retries. | |

**User's choice:** Use confirmed-only failure treatment.
**Notes:** User accepted the recommendation bundle: remove at zero, do not treat pending as sold-out, and return to a retryable normal add control only after confirmed failure.

---

## the agent's Discretion

- Exact text/icon treatment for the short neutral checking state.
- Exact compact vs expanded sizing differences between product card and detail drawer.
- Exact fallback step for weighted `+/-` when no natural increment is available from existing product/cart data.

## Deferred Ideas

- Stale-banner freshness wording is a separate UI cleanup todo and not part of the bounded add UX phase.
- History search todo match was unrelated and not folded into this phase.

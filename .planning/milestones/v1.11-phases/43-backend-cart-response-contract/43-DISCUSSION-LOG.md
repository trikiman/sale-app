# Phase 43: Backend Cart Response Contract - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-06
**Phase:** 43-backend-cart-response-contract
**Areas discussed:** unknown-outcome response, pre-return verification budget, duplicate protection, failure classification

---

## Unknown-outcome response

| Option | Description | Selected |
|--------|-------------|----------|
| Timeout as hard error | Return failure when the backend budget expires, let frontend retry manually. | |
| Return pending | Stop waiting once the response budget is exhausted and return a distinct pending / unknown state for later reconciliation. | ✓ |
| Keep blocking for recovery | Continue inline cart re-checks before responding so one request tries to discover the final truth. | |

**User's choice:** Return pending.
**Notes:** User explicitly meant the timeout budget as "stop waiting and return pending", not "mark as failed". They want the action to stay fast when VkusVill is ambiguous.

---

## Pre-return verification budget

| Option | Description | Selected |
|--------|-------------|----------|
| ~1.0 second | Very aggressive stop-waiting budget; fastest, but easier to misclassify jitter as pending. | |
| ~1.5 seconds | Fast but less brittle budget for proxy jitter, VkusVill latency, and occasional warmup overhead. | ✓ |
| 2.0s+ | Leave more room for backend retries or inline verification before returning. | |

**User's choice:** Use about 1.5 seconds.
**Notes:** User first wondered if 1 second was enough because add is usually fast. After reviewing the current flow, they agreed 1.5 seconds is a better compromise for robustness.

---

## Duplicate protection

| Option | Description | Selected |
|--------|-------------|----------|
| No backend dedupe | Rely entirely on the UI to switch controls fast enough that a second add cannot happen. | |
| Short backend dedupe window | Treat the same `user + product` as one unresolved add for a short window so duplicate upstream adds are not sent during races. | ✓ |
| Longer persistent lock | Keep a longer-lived server lock until final reconciliation completes. | |

**User's choice:** Accepted short backend dedupe as a safety net.
**Notes:** User questioned why dedupe matters if the card will switch into a different control after success. The recommendation was accepted after clarifying that races can still happen across double-taps, detail drawer vs main card, or other sessions. User also stated that all visible copies of the same product should switch to the alternate control rather than register another add.

---

## Failure classification

| Option | Description | Selected |
|--------|-------------|----------|
| Strict error-first | Return errors for timeouts and most upstream uncertainty, only special-case a few recoveries. | |
| Clear-failure-only | Only return real failure for unambiguous cases like unauthenticated user, sold out / invalid product, or clear upstream-unavailable conditions; treat slow ambiguous cases as pending. | ✓ |
| Success-or-error only | Avoid pending state entirely and always coerce into either success or failure. | |

**User's choice:** Clear-failure-only.
**Notes:** User approved the recommendation to reserve hard failure for obvious cases and keep ambiguous upstream behavior out of the error path.

---

## the agent's Discretion

- Exact payload field names for the pending response.
- Exact implementation detail for short-lived pending-attempt tracking.
- Exact reconciliation/logging mechanism after the initial response has returned.

## Deferred Ideas

- Persistent in-card quantity controls after success.
- Cross-page/product-surface syncing so every visible copy of the same product switches to the quantity control.
- Direct numeric quantity entry for weighted items like `0.73 кг`.
- Direct numeric quantity entry for counted items like `2 шт`.

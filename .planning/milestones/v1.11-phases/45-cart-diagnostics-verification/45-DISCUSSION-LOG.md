# Phase 45: Cart Diagnostics & Verification - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-06
**Phase:** 45-cart-diagnostics-verification
**Areas discussed:** diagnostics surface, timing/outcome capture, verification strength

---

## Diagnostics surface

| Option | Description | Selected |
|--------|-------------|----------|
| User-facing diagnostics UI | Add new diagnostic widgets to the MiniApp itself. | |
| Admin/log diagnostics | Surface cart diagnostics via `/admin/status`, admin dashboard, and backend logs. | ✓ |
| Logs only | Keep everything in raw server logs with no admin payload changes. | |

**User's choice:** Use the recommended admin/log diagnostics path.
**Notes:** The phase stays operational and verification-focused rather than adding another end-user UI surface.

---

## Timing and outcome capture

| Option | Description | Selected |
|--------|-------------|----------|
| Final outcome only | Record only whether the add eventually succeeded or failed. | |
| Full attempt lifecycle | Capture add start, add result (`success/pending/failed`), status lookup/reconciliation result, final outcome, and total time-to-truth. | ✓ |
| Deep observability platform | Add broad latency percentile/trend tracking beyond the immediate cart flow. | |

**User's choice:** Use the full attempt lifecycle.
**Notes:** Recommended to keep timeout class and reconciliation source visible enough to explain where slow/ambiguous cart actions actually stalled.

---

## Verification strength

| Option | Description | Selected |
|--------|-------------|----------|
| Lightweight only | A couple of smoke checks and manual confidence. | |
| Strong backend tests + one browser/manual sanity path | Add focused automated backend coverage for the new cart flow and keep one lightweight visible-flow sanity check. | ✓ |
| Full new E2E suite | Build a much larger Playwright/browser matrix for the cart flow. | |

**User's choice:** Use strong backend tests plus one lightweight browser/manual sanity path.
**Notes:** Recommended because it protects the pending/add-status/set-quantity flow without turning this phase into a large new E2E framework project.

---

## the agent's Discretion

- Exact diagnostics field names in route payloads and logs.
- Exact admin dashboard presentation for recent cart attempt diagnostics.
- Exact shape of the lightweight browser/manual verification helper.

## Deferred Ideas

- Historical latency dashboards / percentile tracking beyond recent cart-flow diagnostics.
- Stale-banner wording cleanup from the separate todo.

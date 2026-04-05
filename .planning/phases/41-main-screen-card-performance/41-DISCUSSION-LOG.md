# Phase 41: Main Screen & Card Performance - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `41-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-04-05
**Phase:** 41-main-screen-card-performance
**Areas discussed:** optimization scope, UI stability, data-path changes

---

## Optimization Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Visual redesign + performance | Redesign cards while improving performance | |
| Performance-first with stable UI | Keep the current card UI mostly the same and focus on load/lag | ✓ |

**User's choice:** Keep the UI mostly the same and focus on first-load and card lag.  
**Notes:** User explicitly framed this as optimization work, not a redesign.

---

## Data Path Changes

| Option | Description | Selected |
|--------|-------------|----------|
| Stay on current path only | No alternate API path allowed | |
| Measured comparison | Alternate/private API path allowed only if it is clearly faster and more reliable | ✓ |
| Force new private API path | Commit to reverse-engineering first | |

**User's choice:** Only use a reverse-engineered/private API if it proves clearly faster and more reliable.  
**Notes:** User asked to investigate API ideas but did not want to commit blindly.

---

## Interaction Stability

| Option | Description | Selected |
|--------|-------------|----------|
| Behavior can change if faster | Allow card/cart/detail interaction changes if they help performance | |
| Preserve current interactions | Keep favorites, cart, and detail behavior the same while optimizing | ✓ |

**User's choice:** Preserve current interactions while optimizing.  
**Notes:** Performance work should not silently change favorites/cart/detail UX.

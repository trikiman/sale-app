# Phase 39: Sale Continuity Guardrails - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `39-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-04-05
**Phase:** 39-sale-continuity-guardrails
**Areas discussed:** disappearance grace window, re-entry semantics, bad-cycle handling, diagnostics

---

## Disappearance Grace Window

| Option | Description | Selected |
|--------|-------------|----------|
| Close immediately | Current behavior: one missed merged cycle closes the active sale session | |
| Grace window before close | Require sustained absence before treating the product as gone | ✓ |
| Per-color windows | Use different disappearance windows for green vs red/yellow | |

**User's choice:** Use a grace window. A product should count as truly gone only after it has been missing for **1 hour**.  
**Notes:** User believes the screenshot pattern shows a red item that stayed on sale but was split into fake daily appearances. They explicitly said a single miss should not mean restock/new appearance.

---

## Color Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Same rule for all colors | Keep one disappearance rule across green, red, and yellow | ✓ |
| Stricter for green | Give green a shorter or separate disappearance window | |
| Stricter for red/yellow | Treat slower-updating colors with a larger grace window | |

**User's choice:** Same `1 hour` rule for **all colors**.  
**Notes:** User answered "yes for all".

---

## Bad-Cycle Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Count every miss | Missing from merged data always counts toward disappearance | |
| Ignore failed/stale cycles | A failed or stale cycle means the scraper may have missed the item, so it should not count as disappearance evidence | ✓ |
| Freeze everything on any anomaly | Stop all session updates entirely whenever any scraper is unhealthy | |

**User's choice:** Failed/stale cycles should **not** count toward disappearance.  
**Notes:** User said "if scrapper fail/stale didnt iuts mean he can miss item".

---

## Diagnostics & Logging

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal logs | Keep current logs and rely on manual debugging | |
| Detailed decision logs | Record why a session stayed open, closed, or reopened so false appearances are easy to debug | ✓ |
| User-facing explanation UI | Add explicit continuity-debug explanations directly into history/product UI | |

**User's choice:** Add **deep/detail logs**.  
**Notes:** User wants better detail understanding and easier fixes when this problem happens again. Surface location was left to agent discretion for planning.

---

## the agent's Discretion

- Exact definition of a "healthy cycle" vs "failed/stale" signal
- Exact diagnostic sink (scheduler log, backend log, audit rows, admin debug output)
- Exact code ownership split between `sale_history.py`, `db.py`, and `backend/notifier.py`

## Deferred Ideas

- None raised beyond the out-of-scope todo match, which remains deferred to search/catalog work

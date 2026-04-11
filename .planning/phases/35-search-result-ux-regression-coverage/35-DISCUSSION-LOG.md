# Phase 35: Search Result UX & Regression Coverage - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-04T03:05:00+03:00
**Phase:** 35-search-result-ux-regression-coverage
**Mode:** auto default via `$gsd-next`
**Areas discussed:** Mixed result presentation, card language, implementation shape, regression coverage

---

## Mixed Result Presentation

| Option | Description | Selected |
|--------|-------------|----------|
| Keep the existing card grid and add search-only state cues | Clarify result state within the current card layout when search is active | ✓ |
| Split search results into separate sections | Render live, history, and catalog-only results in distinct groups | |
| Create a dedicated search page layout | Diverge from the existing History page structure during search | |

**User's choice:** Auto-selected the recommended default: keep the current card grid and add search-only state cues.
**Notes:** This keeps Phase 35 scoped to clarity and avoids reopening layout architecture.

---

## Card Language

| Option | Description | Selected |
|--------|-------------|----------|
| Add explicit state labels for live, history-only, and catalog-only matches | Users should not infer result state from color or missing stats alone | ✓ |
| Only improve catalog-only copy | Leave live/history distinction implicit and fix just the `Нет данных` path | |
| Use icons only | Keep copy minimal and rely on symbol differences | |

**User's choice:** Auto-selected the recommended default: add explicit labels for all three result states.
**Notes:** This directly satisfies UI-14 and UI-15.

---

## Implementation Shape

| Option | Description | Selected |
|--------|-------------|----------|
| Extract a small helper and test it | Keep classification logic out of JSX and give Phase 35 a stable test seam | ✓ |
| Branch inline inside `HistoryCard` only | Faster to write but harder to test and evolve | |
| Push UI state derivation into the backend | Change the API contract again just for presentation metadata | |

**User's choice:** Auto-selected the recommended default: extract a small helper and test it.
**Notes:** The backend contract is already stable after Phase 34, so frontend classification is the right layer here.

---

## Regression Coverage

| Option | Description | Selected |
|--------|-------------|----------|
| Keep backend pytest coverage and add frontend helper tests | Combine contract coverage with presentation-state coverage | ✓ |
| Backend tests only | Trust the UI rendering to stay correct without a frontend seam | |
| Frontend tests only | Drop the API-level mixed-result regression suite from Phase 34 | |

**User's choice:** Auto-selected the recommended default: keep backend coverage and add frontend helper tests.
**Notes:** This is the lowest-friction way to satisfy QA-01 without introducing a new test framework.

---

## the agent's Discretion

- Exact Russian wording for the state labels and support copy
- Minimal CSS needed for the new chips and explanatory text
- Helper API shape for the new frontend test seam

## Deferred Ideas

- Remote VkusVill search parity remains out of scope
- Search ranking and grouped result sections remain future UX work

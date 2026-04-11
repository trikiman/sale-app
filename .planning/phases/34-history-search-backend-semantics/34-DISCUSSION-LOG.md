# Phase 34: History Search Backend Semantics - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-04T01:43:29.8221170+03:00
**Phase:** 34-history-search-backend-semantics
**Mode:** default selection via `$gsd-next`
**Areas discussed:** Search dataset scope, search filter semantics, result contract, regression coverage

---

## Search Dataset Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Full local catalog when search is active | Remove the implicit `total_sale_count > 0` gate and search all rows in `product_catalog` without calling remote VkusVill search | ✓ |
| History-only dataset plus text filter | Keep current history behavior and only filter among products with recorded sale history | |
| Remote VkusVill search parity | Expand search by querying VkusVill directly whenever the local catalog is incomplete | |

**User's choice:** Defaulted to the recommended option: full local catalog when search is active.
**Notes:** This matches the milestone goal and the originating todo while preserving the explicit out-of-scope boundary around remote search parity.

---

## Search Filter Semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Lift only implicit history scoping | Search uses the full catalog, but explicit user filters like `group`, `subgroup`, and sale-type filters still apply if set intentionally | ✓ |
| Ignore all filters during search | Search always returns the broadest possible result set and bypasses every other control | |
| Keep history-scoped group/filter behavior | Search remains constrained by the same history-only chip and filter scope as the default page | |

**User's choice:** Defaulted to the recommended option: remove only hidden history scoping and keep explicit user filters intentional.
**Notes:** `HistoryPage.jsx` already moves group chips to `scope=all` while searching, so this choice aligns the backend semantics with the current frontend contract instead of introducing a new search-only mode.

---

## Result Contract

| Option | Description | Selected |
|--------|-------------|----------|
| Keep one History API shape for all matches | Catalog-only products return the existing fields with zero/null sale history values and `is_currently_on_sale = false` | ✓ |
| Introduce a separate catalog-search result type | Return a different DTO for no-history products and make the client branch on result kind | |
| Hide catalog-only items until Phase 35 | Delay zero-history results until the UI state treatment is finished | |

**User's choice:** Defaulted to the recommended option: keep a single response contract for all search hits.
**Notes:** `HistoryPage.jsx` already knows how to render no-data/ghost cards, so Phase 34 can unlock the data semantics now and leave visual clarity polish to Phase 35.

---

## Regression Coverage

| Option | Description | Selected |
|--------|-------------|----------|
| Add backend endpoint regression tests | Use pytest + FastAPI `TestClient` fixtures for live-sale, history-only, and catalog-only search cases | ✓ |
| Rely on manual browser verification only | Check the History page by hand after implementation and skip automated coverage | |
| Add frontend-only tests first | Treat this mainly as a UI concern and delay backend contract tests | |

**User's choice:** Defaulted to the recommended option: backend endpoint regression tests.
**Notes:** The current backend test suite already uses `TestClient`, and this phase is primarily about query semantics rather than presentation.

---

## the agent's Discretion

- Exact query refactor shape in `backend/main.py`
- Test file placement and fixture setup
- Minimal inline documentation/comments for search-mode behavior

## Deferred Ideas

- Remote VkusVill search parity beyond the local catalog remains deferred to future requirement `SRCH-04`
- Live/history/catalog card-state messaging and other visual polish stays in Phase 35


# Phase 35: Search Result UX & Regression Coverage - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Make mixed History search results understandable at a glance and protect that presentation with automated regression coverage. This phase covers search-result state language, small card-level UI cues, and frontend/unit-level protection around those states. It does not change the backend search contract from Phase 34, add remote VkusVill search parity, or redesign the broader History page layout.

</domain>

<decisions>
## Implementation Decisions

### Mixed Search Result Presentation
- **D-01:** Keep the existing card grid and click behavior. Phase 35 should clarify result state within the current `HistoryCard` layout instead of introducing tabs, separate result sections, or a different search page.
- **D-02:** The new state language is most important while a search query is active. Prefer search-mode-only visual cues so the default non-search History page stays familiar and less noisy.
- **D-03:** Distinguish three search result states explicitly:
  - live-on-sale match
  - history-only match
  - catalog-only match with no sale history yet

### Card Language & Cues
- **D-04:** Live-on-sale matches should keep the existing sale badge/live dot and gain an explicit status label so users do not have to infer "currently on sale" from color alone.
- **D-05:** History-only matches should show a neutral "seen on sale before" style label rather than looking identical to live results.
- **D-06:** Catalog-only matches should no longer stop at generic `Нет данных`. They need intentional wording that makes it clear the product exists in the local catalog but has not had a recorded sale yet.

### Implementation Shape
- **D-07:** Extract the mixed-result classification into a small shared helper instead of burying state branching directly inside JSX. This gives Phase 35 a stable test seam and keeps `HistoryPage.jsx` readable.
- **D-08:** Reuse existing card structure and CSS naming where possible. Add only the minimum new classes needed for state labels and explanatory text.

### Regression Coverage
- **D-09:** Keep the Phase 34 backend pytest coverage as the contract-level guardrail and add frontend/unit coverage for the state-classification helper and its user-facing labels.
- **D-10:** Do not pull in a new test framework. Follow the repo’s existing `node:test` pattern used by `miniapp/src/*.test.mjs`.

### the agent's Discretion
- Exact Russian copy for the three result-state labels and supporting text
- Whether the helper returns one object or a pair of smaller helpers
- Exact CSS palette/border treatment for the new state chips as long as it stays consistent with the existing card language

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope
- `.planning/ROADMAP.md` — Phase 35 goal, requirements mapping, and success criteria
- `.planning/REQUIREMENTS.md` — UI-14, UI-15, and QA-01 define the mixed-result clarity and coverage requirements
- `.planning/PROJECT.md` — current milestone framing and future-search boundaries

### Prior Phase Contract
- `.planning/phases/34-history-search-backend-semantics/34-CONTEXT.md` — backend search semantics and response-shape decisions that Phase 35 must preserve
- `.planning/phases/34-history-search-backend-semantics/34-VERIFICATION.md` — verified search-result classes and the existing backend regression gate

### Existing UI & Styles
- `miniapp/src/HistoryPage.jsx` — current card layout, ghost/no-data path, live badge/dot handling, and search-mode behavior
- `miniapp/src/index.css` — current `hcard-*` and `history-*` styling hooks used by the History page

### Existing Tests
- `backend/test_history_search.py` — backend contract coverage for live/history/catalog-only search results
- `miniapp/src/productMeta.test.mjs` — existing `node:test` pattern for small frontend helpers
- `miniapp/src/detailDrawerStyles.test.mjs` — existing CSS assertion pattern for frontend styling rules
- `.planning/codebase/TESTING.md` — current test strategy and lightweight frontend test conventions

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `miniapp/src/HistoryPage.jsx:HistoryCard` already has a clean card shell, image area, badge zone, stats section, and no-data block that Phase 35 can extend without changing page structure
- `miniapp/src/index.css` already defines `hcard-type-badge`, `hcard-live-dot`, `hcard-no-data`, and related card primitives
- `backend/test_history_search.py` already exercises the three result classes at the API layer, so frontend coverage can stay focused on classification/presentation

### Established Patterns
- Frontend helper logic is already tested with lightweight `node:test` modules rather than a heavier UI runner
- History cards already distinguish "has history data" vs "no data" structurally; Phase 35 mainly needs better state wording and clearer search-mode semantics
- Search-mode result scope is now stable after Phase 34, so UI code can trust mixed result sets to arrive from the current `/api/history/products` endpoint

### Integration Points
- `HistoryCard` in `miniapp/src/HistoryPage.jsx` is the primary rendering point for state labels and explanatory text
- `miniapp/src/index.css` is the right place for any new state-pill and support-copy styling
- A new small helper module under `miniapp/src/` is the cleanest seam for Phase 35 unit tests

</code_context>

<specifics>
## Specific Ideas

- A search like `цезарь` should make it obvious which result is on sale now, which one had prior sales only, and which one is merely present in the catalog.
- Search-only state cues are preferable to globally noisier cards because the default History page still mostly shows history-backed products.
- Catalog-only matches should feel intentional, not like a half-broken analytics card.

</specifics>

<deferred>
## Deferred Ideas

### Reviewed Todos (not folded)
- `2026-04-02-history-search-shows-all-matching-products-from-catalog.md` — Phase 34 already solved the dataset completeness portion; Phase 35 focuses on presentation clarity rather than reopening backend search scope

- Remote VkusVill search parity beyond the local catalog snapshot — still future work, not part of this UI/coverage phase
- Search ranking or sectioned result groups — separate UX capability, out of scope for this milestone step

</deferred>

---

*Phase: 35-search-result-ux-regression-coverage*
*Context gathered: 2026-04-04*

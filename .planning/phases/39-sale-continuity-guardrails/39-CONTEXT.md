# Phase 39: Sale Continuity Guardrails - Context

**Gathered:** 2026-04-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Stop fake sale re-appearances caused by transient scrape misses so continuous sales remain one continuous session. This phase covers session-close/reopen semantics, "new item" re-entry rules, and diagnostic logging around those decisions. It does not rebalance scheduler cadence, add new user-facing failure UI, or optimize the main screen.

</domain>

<decisions>
## Implementation Decisions

### Sale Exit Confirmation
- **D-01:** A product is not truly "gone" until it has been absent from merged sale data for **1 hour**. One missed cycle, or a few missed cycles inside that hour, must not close the active sale session.
- **D-02:** The same 1-hour disappearance rule applies to **all colors**. Phase 39 does not use separate green/red/yellow exit windows.

### Bad Cycle Tolerance
- **D-03:** Failed or stale scraper cycles do **not** count toward disappearance confirmation. If the scraper/source health is bad, the system must treat the product state as unknown rather than gone.
- **D-04:** A product may count as a true re-entry/new appearance only after a **confirmed exit** under the 1-hour rule and then a later healthy reappearance. If the scraper merely missed it somehow, that is not a restock/new appearance.

### Diagnostics & Repairability
- **D-05:** Add detailed diagnostic logging for session close/reopen decisions so it is easy to understand why a product was kept active, marked gone, or treated as newly returned.
- **D-06:** Diagnostic detail should include the product ID, sale type, cycle health or stale/failure reason, how long the item has been missing, and the explicit reason the system chose to keep, close, or reopen the session.

### the agent's Discretion
- Exact implementation of "healthy cycle" vs "failed/stale cycle", as long as failed/stale cycles never count toward disappearance.
- Exact storage/surface for diagnostics first (scheduler log, backend log, DB audit rows, admin debug output), as long as the detail is deep enough to debug future false re-appearances quickly.
- Whether the new-entry rule is enforced primarily in `sale_history.py`, `backend/notifier.py`, or a shared helper, as long as both history and notifier behavior stay aligned.

</decisions>

<specifics>
## Specific Ideas

- User example: a red item appears in history on `2026-03-31 04:55`, then again on `2026-03-31 21:09`, `2026-04-01 21:05`, `2026-04-02 21:20`, `2026-04-03 21:09`, and `2026-04-04 21:17`, even though the user believes it stayed on sale and never truly restocked. The system should treat this pattern as a likely scraper/session-splitting bug, not a sequence of real daily re-entries.
- Red items are expected to restock much more rarely than green items, so a transient miss must not create fake daily appearances.
- If the scraper misses an item somehow, continuity should be preserved and the reason should be visible in deep logs for easier debugging and repair.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope
- `.planning/ROADMAP.md` — Phase 39 goal, requirements mapping, and success criteria
- `.planning/REQUIREMENTS.md` — HIST-08, BOT-07, and OPS-02 define the continuity/newness contract
- `.planning/PROJECT.md` — milestone framing for false re-appearances, stale cycles, and reliability work
- `.planning/STATE.md` — current milestone notes and known bug summary

### Existing Sale Continuity & Notification Logic
- `database/sale_history.py` — current sale session close/open logic; active sessions close immediately when a product is missing from one merged cycle
- `database/db.py` — `seen_products`, `get_new_products`, `mark_product_seen`, and `notification_history` primitives
- `backend/notifier.py` — current "new products" detection plus mark-all-seen flow after notifications
- `scheduler_service.py` — sequential red/yellow/green cycle, per-scraper status, and notifier trigger order
- `backend/main.py` — `/api/products` stale/green-missing signals and admin-status freshness exposure that may help identify unhealthy cycles

### Prior Decisions & Codebase Guides
- `.planning/phases/33-group-subgroup-notifications/33-CONTEXT.md` — keep the existing scheduler -> merge -> notifier pipeline and reuse `notification_history` dedupe
- `.planning/codebase/ARCHITECTURE.md` — scheduler pipeline, JSON/DB flow, and backend/frontend integration baseline
- `.planning/codebase/CONVENTIONS.md` — current logging and error-handling patterns
- `.planning/codebase/TESTING.md` — current testing gaps around scheduler/session behavior

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `database/sale_history.py:record_sale_appearances()` already centralizes active-session close/open decisions for every merged cycle.
- `database/db.py:was_notification_sent()` and `database/db.py:record_notification()` already provide notification dedupe primitives that can stay aligned with any new re-entry logic.
- `scheduler_service.py` already knows per-scraper outcomes (`OK`, `ERROR`, `TIMEOUT`, file-not-updated warnings), which can feed "healthy cycle" guardrails.
- `backend/main.py:/api/products` already derives live `dataStale` / `greenMissing` signals from source freshness at request time.

### Established Patterns
- The pipeline is still sequential: red -> yellow -> green -> merge -> notifier. No parallel jobs should be introduced in this phase.
- Downstream state is derived from the merged sale snapshot after each cycle; the current bug is that a single bad snapshot is treated as a true disappearance.
- Notification dedupe today is time-window based (`notification_history` for 24h) while "newness" is still based on `seen_products`, so these semantics need to stay coherent after the fix.
- Logging is file/logger based, not structured telemetry. Debuggability improvements should fit that style unless a lightweight audit structure is clearly better.

### Integration Points
- `database/sale_history.py` is the main place to introduce disappearance grace-window logic and protect active sessions during bad cycles.
- `backend/notifier.py` and/or `database/db.py` must align "new item" detection with confirmed exits so fake re-entries stop triggering.
- `scheduler_service.py` and freshness checks in `backend/main.py` are the obvious sources for cycle-health/staleness evidence.
- Regression coverage will likely live in backend pytest files because scheduler/session logic currently has no dedicated test protection.

</code_context>

<deferred>
## Deferred Ideas

### Reviewed Todos (not folded)
- `2026-04-02-history-search-shows-all-matching-products-from-catalog.md` — surfaced by keyword match, but remains out of Phase 39 because it is a search/catalog completeness issue rather than a session-continuity decision.

</deferred>

---

*Phase: 39-sale-continuity-guardrails*
*Context gathered: 2026-04-05*

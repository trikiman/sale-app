# Phase 40: Freshness-Aware Scheduler & Alerts - Context

**Gathered:** 2026-04-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Rebalance the scheduler so green refreshes happen much more often than red/yellow, expose per-source freshness clearly, and warn users/admins when any sale data is stale. This phase covers scheduler cadence, freshness metadata, stale/failure warning behavior, and reuse of the last valid per-color snapshots. It does not redesign the MiniApp, change sale-continuity rules from Phase 39, or add Telegram push alerts for all users.

</domain>

<decisions>
## Implementation Decisions

### Scheduler Cadence
- **D-01:** Keep the existing full `ALL` cycle as the normal sequential run for `red + yellow + green + merge + notifier`.
- **D-02:** Target the `ALL` cycle every **5 minutes**.
- **D-03:** Between full cycles, schedule extra `GREEN-only` runs on a **1-minute target start interval**.
- **D-04:** Green timing is completion-based, not fixed-slot overlap: if a green run finishes in 30s, wait 30s; if it finishes in 50s, wait 10s; if it takes longer than 60s, start the next due step immediately after finish.
- **D-05:** The scheduler remains strictly sequential with **no overlap**.
- **D-06:** The full `ALL` cycle has priority. If running another green-only pass would make the next full cycle late, skip that extra green run.

### Freshness Rules
- **D-07:** Treat **all colors** as stale after **10 minutes** without a fresh valid update.
- **D-08:** When a color is stale or failed, keep serving the **last valid snapshot** for that color instead of hiding it.
- **D-09:** Merge/notifier logic should use the freshest valid per-color snapshots rather than assuming every color was refreshed in the same cycle.

### Warning Surfaces
- **D-10:** If any color data is older than 10 minutes, **warn all users** in the MiniApp.
- **D-11:** Reuse the **existing warning/banner surface** in the MiniApp rather than inventing a brand-new alert pattern.
- **D-12:** Also expose the same per-source freshness/staleness state in admin status and logs.
- **D-13:** Do **not** add a new Telegram push alert to all users in this phase; warning everyone means the MiniApp warning surface plus admin/log visibility.

### the agent's Discretion
- Exact due-job implementation for `ALL` vs `GREEN-only` scheduling, as long as the 5-minute full-cycle target, 1-minute green target, no-overlap rule, and `ALL` priority are preserved.
- Exact freshness fields added to backend/admin payloads, as long as per-source freshness is obvious.
- Exact wording of the stale warning banner, as long as it clearly tells users data may be outdated.

</decisions>

<specifics>
## Specific Ideas

- User wants the cadence to feel like: full cycle, then repeated green-only opportunities each minute until the next 5-minute full cycle is due.
- The user explicitly wants completion-based waiting: if a green run ends early, wait the remainder to the 60-second target; if it runs longer than 60 seconds, continue immediately with the next due step.
- The user wants to keep showing the last valid data instead of blanking a color out.
- The user explicitly asked to **reuse the existing site warning** rather than inventing a different warning surface.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope
- `.planning/ROADMAP.md` — Phase 40 goal, requirements mapping, and success criteria
- `.planning/REQUIREMENTS.md` — SCRP-10, SCRP-11, SCRP-12, and OPS-03 define the scheduler/freshness/alert contract
- `.planning/PROJECT.md` — milestone framing for green-first freshness and stale-data visibility
- `.planning/STATE.md` — current milestone notes and known scheduler freshness bug summary

### Existing Scheduler & Freshness Logic
- `scheduler_service.py` — current single-interval sequential cycle, per-scraper results, retry flow, and notifier trigger order
- `backend/main.py` — `/api/products` stale detection, `greenMissing`, `/admin/status`, and `/admin/logs`
- `miniapp/src/App.jsx` — existing stale-data and green-warning banners that should be reused rather than replaced
- `backend/notifier.py` — current post-merge notifier path that must continue using the freshest valid snapshot rules

### Prior Decisions & Codebase Guides
- `.planning/phases/39-sale-continuity-guardrails/39-CONTEXT.md` — continuity and bad-cycle semantics that freshness scheduling must preserve
- `.planning/phases/33-group-subgroup-notifications/33-CONTEXT.md` — keep the scheduler -> merge -> notifier pipeline shape
- `.planning/codebase/ARCHITECTURE.md` — existing sequential pipeline and frontend/backend data flow
- `.planning/codebase/CONVENTIONS.md` — current logging/error-handling patterns

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scheduler_service.py:run_full_cycle()` already centralizes scraper order, retry logic, and status strings per color.
- `backend/main.py:/api/products` already computes `dataStale`, `staleInfo`, and `greenMissing` from source file freshness.
- `backend/main.py:/admin/status` and `/admin/logs` already provide the obvious operator surfaces for richer freshness data.
- `miniapp/src/App.jsx` already renders stale-warning and green-warning banners that can be extended instead of replaced.

### Established Patterns
- The scheduler currently runs one strictly sequential pipeline with a single interval and no overlap.
- The app already keeps showing the last merged snapshot while warning about staleness instead of blanking the page.
- Admin visibility is file/log driven, not a separate monitoring product.
- The MiniApp already accepts freshness metadata from `/api/products` and turns it into banners.

### Integration Points
- `scheduler_service.py` is the place to introduce due-job scheduling for `ALL` vs `GREEN-only`.
- `backend/main.py` must expose per-source freshness so both admin and MiniApp can tell which color is stale.
- `miniapp/src/App.jsx` should reuse the current warning surface to warn all users when any color is stale.
- `backend/notifier.py` and merge flow should keep operating on the freshest valid per-color data rather than same-cycle-only assumptions.

</code_context>

<deferred>
## Deferred Ideas

### Reviewed Todos (not folded)
- `2026-04-02-history-search-shows-all-matching-products-from-catalog.md` — surfaced by keyword match, but stays out of Phase 40 because it is a search/catalog completeness issue rather than scheduler freshness work.

- Telegram push alerts to all users for stale/failure conditions — future consideration if the MiniApp banner is not enough.

</deferred>

---

*Phase: 40-freshness-aware-scheduler-alerts*
*Context gathered: 2026-04-05*

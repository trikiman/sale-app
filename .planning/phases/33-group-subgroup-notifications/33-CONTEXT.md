# Phase 33: Group/Subgroup Notifications - Context

**Gathered:** 2026-04-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Extend Telegram sale notifications so a user is alerted when a sale product belongs to one of their favorited groups or subgroups. This phase covers notifier-side matching, deduplication, and message copy for those matches. It does not add new favorite storage, new scheduler infrastructure, or new UI.

</domain>

<decisions>
## Implementation Decisions

### Match Source & Favorite Key Handling
- **D-01:** Extend the existing favorite notification flow in `backend/notifier.py` to evaluate category favorites from `favorite_categories` alongside product favorites. Category keys remain exact strings in the existing formats `group:X` and `subgroup:X/Y`.
- **D-02:** Use merged product data from `data/proposals.json` as the primary match source because the notifier already runs on that file after `scrape_merge.py`. If a product record is missing `group` or `subgroup`, fall back to `product_catalog` by `product_id` so category notifications still work while runtime JSON catches up.
- **D-03:** Matching is exact, not fuzzy. `group:X` matches any product whose group is exactly `X`. `subgroup:X/Y` matches only products whose group is `X` and subgroup is exactly `Y`.

### Deduplication & Notification Flow
- **D-04:** Build one per-user candidate map keyed by `product_id` that merges matches from product favorites, group favorites, and subgroup favorites before any message is sent.
- **D-05:** Reuse the existing `notification_history` / `was_notification_sent(..., hours=24)` gate as the duplicate-suppression mechanism. Do not create separate history rows per match reason.
- **D-06:** Keep the existing scheduler flow unchanged: `scheduler_service.py` runs `backend/notifier.py` after merge, and Phase 33 extends that script rather than creating a parallel notification job.

### Telegram Message Behavior
- **D-07:** Keep the current per-user notification structure: one header plus per-product messages with existing inline buttons.
- **D-08:** Each product message should include one explicit match-reason line using the most specific category reason available. Precedence: subgroup match first, then group match, then product-favorite fallback if no category reason exists.
- **D-09:** If multiple reasons match the same product, show only the single most specific visible reason in the message. Keep the full reason set internal for dedupe/debugging only.

### the agent's Discretion
- Exact helper placement between `backend/notifier.py` and `database/db.py`
- Whether the `product_catalog` fallback is implemented as one preload query or small targeted lookups
- Exact Russian wording for the match-reason line and header copy

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope
- `.planning/ROADMAP.md` — Phase 33 goal and success criteria for group/subgroup Telegram alerts
- `.planning/REQUIREMENTS.md` — BOT-06 requirement for category-based notifications
- `.planning/STATE.md` — Current milestone status and notes from phases 29-32

### Category Hierarchy & Favorites
- `.planning/phases/29-subgroup-data-layer/29-CONTEXT.md` — Group/subgroup data model decisions from the data-layer phase
- `backend/main.py` — `/api/favorites/{user_id}/categories` contract and `group:X` / `subgroup:X/Y` key formats
- `database/db.py` — `favorite_categories`, `favorite_products`, and notification history helpers

### Notification Pipeline
- `scheduler_service.py` — Existing scheduler step that runs favorite notifications after merge
- `backend/notifier.py` — Current favorite notification cycle, formatting, and duplicate gate
- `scrape_merge.py` — Merge step that enriches `proposals.json` with `group` and `subgroup` when category data is available

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/notifier.py:Notifier.load_products()` already loads merged sale products from `data/proposals.json`
- `backend/notifier.py:Notifier.notify_favorites()` already sends per-user favorite alerts with Telegram buttons and records notification history
- `database/db.py:get_user_favorite_categories()` and `database/db.py:get_user_favorite_products()` already expose the two favorite sources this phase needs to merge
- `database/db.py:was_notification_sent()` and `database/db.py:record_notification()` already provide the 24-hour dedupe path

### Established Patterns
- Scheduler-driven notification cycle: merge first, then run notifier as a standalone backend script
- Favorites are stored separately by type: product favorites in `favorite_products`, category favorites in `favorite_categories`
- Category favorites already use stable serialized keys: `group:X` and `subgroup:X/Y`
- Telegram notifications are batched per user with a header, up to 10 product messages, and inline buttons

### Integration Points
- `backend/notifier.py:get_favorite_alerts()` or a sibling helper is the natural place to merge category matches with product matches
- `backend/notifier.py:notify_favorites()` is the existing send path to extend with category-reason metadata
- `scrape_merge.py` and `product_catalog` together define the two sources for `group` / `subgroup` data

</code_context>

<specifics>
## Specific Ideas

- Local codebase inspection found that the current checked-in `data/proposals.json` sample contains sale products but no populated `group` / `subgroup` fields, even though `scrape_merge.py` now supports them. That makes a DB fallback important for robustness.
- Keep Phase 33 inside the backend notifier path rather than moving logic into bot polling handlers. The scheduler already owns the scrape-merge-notify sequence.

</specifics>

<deferred>
## Deferred Ideas

### Reviewed Todos (not folded)
- `2026-04-02-history-search-shows-all-matching-products-from-catalog.md` — surfaced by keyword match, but stays out of Phase 33 because it is a history/catalog completeness concern rather than a notification behavior change

</deferred>

---

*Phase: 33-group-subgroup-notifications*
*Context gathered: 2026-04-03*

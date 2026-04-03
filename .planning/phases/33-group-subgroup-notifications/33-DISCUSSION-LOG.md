# Phase 33: Group/Subgroup Notifications - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-03T08:36:40.3456332+03:00
**Phase:** 33-group-subgroup-notifications
**Mode:** auto default via `$gsd-next`
**Areas discussed:** Match source, duplicate handling, Telegram message behavior, integration path

---

## Match Source

| Option | Description | Selected |
|--------|-------------|----------|
| Merged JSON first with DB fallback | Reuse `data/proposals.json` in the notifier, but look up `product_catalog` when `group` or `subgroup` is missing | ✓ |
| Database only | Match everything from `product_catalog` and ignore merged JSON category fields | |
| Merged JSON only | Assume `proposals.json` always has category hierarchy and skip fallback logic | |

**User's choice:** Auto-selected the recommended default: merged JSON first with fallback to `product_catalog`.
**Notes:** Existing notifier flow already reads `data/proposals.json`, but the current local sample has zero populated `group` / `subgroup` fields, so fallback keeps the feature resilient.

---

## Duplicate Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Merge matches by product ID before send | Product, group, and subgroup matches collapse to one candidate product per user and reuse existing 24-hour history | ✓ |
| Send one alert per match reason | Product favorites and category favorites each trigger their own alert | |
| Add separate dedupe tables per favorite type | Track product and category alerts independently | |

**User's choice:** Auto-selected the recommended default: merge all match reasons into one per-product candidate set before sending.
**Notes:** This satisfies the roadmap requirement to avoid duplicate alerts when both a product and its group/subgroup are favorited.

---

## Telegram Message Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Show the most specific visible reason | Add one reason line per product message with precedence subgroup > group > product favorite fallback | ✓ |
| Show all matching reasons | List every favorite reason that matched the product | |
| Omit the reason from the message | Send the existing product message without telling the user what matched | |

**User's choice:** Auto-selected the recommended default: show one visible reason using the most specific category match.
**Notes:** This keeps messages readable while still fulfilling the Phase 33 requirement that the notification indicates which group/subgroup matched.

---

## Integration Path

| Option | Description | Selected |
|--------|-------------|----------|
| Extend `backend/notifier.py` in the current scheduler cycle | Keep scrape → merge → notify intact and add category matching to the existing backend script | ✓ |
| Move logic into `bot/notifier.py` | Shift category notifications into bot-side notification helpers | |
| Create a separate notification worker | Add a new standalone job just for group/subgroup alerts | |

**User's choice:** Auto-selected the recommended default: extend `backend/notifier.py` inside the current scheduler flow.
**Notes:** `scheduler_service.py` already runs `backend/notifier.py` after merge, so this is the lowest-risk path and matches the current architecture.

---

## the agent's Discretion

- Exact helper extraction and naming inside `backend/notifier.py`
- Query shape for the `product_catalog` fallback
- Final Russian phrasing for the visible reason line

## Deferred Ideas

- `2026-04-02-history-search-shows-all-matching-products-from-catalog.md` remains deferred because it is outside notification scope

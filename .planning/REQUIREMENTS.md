# Requirements: v1.7 Categories & Subgroups

**Milestone:** v1.7
**Created:** 2026-04-02
**Goal:** Add proper group/subgroup category structure across the app with favorite groups/subgroups and notifications.

## Data / Scraping

- [ ] **DATA-01**: Category scraper stores `{group, subgroup}` for each product (not just flat category name)
- [ ] **DATA-02**: Existing 16K products in `category_db.json` are re-scraped with subgroup data
- [ ] **DATA-03**: Product catalog DB (`product_catalog` table) has group and subgroup columns populated from category_db

## Main Page UI

- [ ] **UI-08**: Group category chips displayed on main page (existing behavior, preserved)
- [ ] **UI-09**: Selecting a group shows a second row of subgroup chips for that group
- [ ] **UI-10**: Subgroup row hidden when no group is selected
- [ ] **UI-11**: Subgroup row hidden when the selected group has only 1 subgroup
- [ ] **UI-12**: User can tap ⭐ on a group/subgroup chip to favorite the group/subgroup itself (not individual products)
- [ ] **UI-13**: Products correctly filtered by selected group and subgroup

## History Page

- [ ] **HIST-01**: History page shows group filter chips (category groups)
- [ ] **HIST-02**: Selecting a group on history page shows subgroup chips (same drill-down UX as main page)
- [ ] **HIST-03**: Same subgroup hide rules apply (no group selected → no subgroups, 1 subgroup → no row)
- [ ] **HIST-04**: Group/subgroup ⭐ favorite works on history page too

## Favorites

- [ ] **FAV-03**: Group/subgroup favorites stored per-user in DB (separate from product favorites)
- [ ] **FAV-04**: Favorites view shows group/subgroup favorites as single entries (e.g., "⭐ Торты") alongside individual product ⭐s

## Notifications

- [ ] **BOT-06**: Telegram notifier checks group/subgroup favorites — when ANY product in a favorited group/subgroup goes on sale, user gets notified

## Out of Scope

- Search completeness for non-sale products (tracked as todo)
- Subgroup scraping for VkusVill "Супермаркет" sub-categories (already flat)

## Traceability

| Requirement | Phase |
|-------------|-------|
| DATA-01     | 29    |
| DATA-02     | 29    |
| DATA-03     | 29    |
| UI-08       | 30    |
| UI-09       | 30    |
| UI-10       | 30    |
| UI-11       | 30    |
| UI-12       | 31    |
| UI-13       | 30    |
| HIST-01     | 32    |
| HIST-02     | 32    |
| HIST-03     | 32    |
| HIST-04     | 32    |
| FAV-03      | 31    |
| FAV-04      | 31    |
| BOT-06      | 33    |

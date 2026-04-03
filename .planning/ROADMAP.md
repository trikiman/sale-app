# Roadmap: VkusVill Sale Monitor

**Created:** 2026-03-30
**Status:** v1.7 in progress

## Milestones

- ✅ **v1.0 Bug Fix & Stability** — Phases 1-9 (shipped 2026-03-31)
- ✅ **v1.1 Testing & QA** — Phases 10-12, 71 tests (shipped 2026-03-31)
- ✅ **v1.2 Price History** — Phases 13-18 (shipped 2026-04-01)
- ✅ **v1.3 Performance & Optimization** — Phases 19-20 (shipped 2026-04-01)
- ✅ **v1.4 Proxy Centralization** — Phases 21-23 (shipped 2026-04-01)
- ✅ **v1.5 History Search & Polish** — Phases 24-26 (shipped 2026-04-01)
- ✅ **v1.6 Green Scraper Robustness** — Phases 27-28 (shipped 2026-04-02)
- 🔧 **v1.7 Categories & Subgroups** — Phases 29-33

## Phases

<details>
<summary>✅ v1.0 Bug Fix & Stability (Phases 1-9) — SHIPPED 2026-03-31</summary>

See: `.planning/milestones/v1.0-ROADMAP.md`

</details>

<details>
<summary>✅ v1.1 Testing & QA (Phases 10-12) — SHIPPED 2026-03-31</summary>

See: `.planning/milestones/v1.1-ROADMAP.md`

</details>

<details>
<summary>✅ v1.2 Price History (Phases 13-18) — SHIPPED 2026-04-01</summary>

See: `.planning/milestones/v1.2-ROADMAP.md`

</details>

<details>
<summary>✅ v1.3 Performance & Optimization (Phases 19-20) — SHIPPED 2026-04-01</summary>

See: `.planning/milestones/v1.3-ROADMAP.md`

</details>

<details>
<summary>✅ v1.4 Proxy Centralization (Phases 21-23) — SHIPPED 2026-04-01</summary>

See: `.planning/milestones/v1.4-ROADMAP.md`

</details>

<details>
<summary>✅ v1.5 History Search & Polish (Phases 24-26) — SHIPPED 2026-04-01</summary>

See: `.planning/milestones/v1.5-ROADMAP.md`

</details>

<details>
<summary>✅ v1.6 Green Scraper Robustness (Phases 27-28) — SHIPPED 2026-04-02</summary>

See: `.planning/milestones/v1.6-ROADMAP.md`

</details>

### v1.7 Categories & Subgroups

#### Phase 29: Subgroup Data Layer
**Goal:** Scrape VkusVill subgroups and add group/subgroup columns to the data pipeline.
**Requirements:** DATA-01, DATA-02, DATA-03
**Success Criteria:**
1. `scrape_categories.py` navigates each category page and extracts subgroup links
2. `category_db.json` stores `{name, group, subgroup}` for each product (16K+ products)
3. `product_catalog` DB table has `group` and `subgroup` columns populated from category_db
4. `scrape_merge.py` uses group/subgroup from category_db when building proposals.json
5. Running scraper on EC2 produces valid data with subgroups populated

#### Phase 30: Main Page Group/Subgroup UI
**Goal:** Add subgroup drill-down to the main page category filter.
**Requirements:** UI-08, UI-09, UI-10, UI-11, UI-13
**Success Criteria:**
1. Main page group chips show VkusVill groups (existing behavior preserved)
2. Selecting a group reveals a second row of subgroup chips
3. No group selected → no subgroup row visible
4. Group with only 1 subgroup → no subgroup row visible
5. Selecting a subgroup filters products to that subgroup only
6. Products correctly assigned to their group/subgroup

#### Phase 31: Group/Subgroup Favorites
**Goal:** Enable favoriting groups/subgroups as single entries (not individual products).
**Requirements:** UI-12, FAV-03, FAV-04
**Success Criteria:**
1. ⭐ button visible on each group/subgroup chip
2. Tapping ⭐ saves the group/subgroup itself as a favorite (stored per-user in DB)
3. Favorites view shows group/subgroup entries (e.g., "⭐ Торты") alongside product favorites
4. Un-favoriting a group/subgroup removes the single entry (doesn't affect individual product favorites)

#### Phase 32: History Page Groups & Favorites
**Goal:** Add the same group/subgroup filtering and favorites to the history page.
**Requirements:** HIST-01, HIST-02, HIST-03, HIST-04
**Success Criteria:**
1. History page shows group filter chips
2. Selecting a group shows subgroup chips (same UX as main page)
3. Same hide rules: no group → no subgroups, 1 subgroup → no row
4. Group/subgroup ⭐ favorite button works on history page
5. History products filtered correctly by group/subgroup

#### Phase 33: Group/Subgroup Notifications
**Goal:** Telegram notifier alerts users when products in their favorited groups/subgroups go on sale.
**Requirements:** BOT-06
**Success Criteria:**
1. Notifier checks user's group/subgroup favorites alongside product favorites
2. When a product in a favorited group/subgroup goes on sale → Telegram notification sent
3. No duplicate notifications if both a product AND its group/subgroup are favorited
4. Notification message indicates which group/subgroup matched

## Progress

| Phase | Milestone | Status | Completed |
|-------|-----------|--------|-----------|
| 1-9 | v1.0 | ✅ Complete | 2026-03-31 |
| 10-12 | v1.1 | ✅ Complete | 2026-03-31 |
| 13-18 | v1.2 | ✅ Complete | 2026-04-01 |
| 19-20 | v1.3 | ✅ Complete | 2026-04-01 |
| 21-23 | v1.4 | ✅ Complete | 2026-04-01 |
| 24-26 | v1.5 | ✅ Complete | 2026-04-01 |
| 27-28 | v1.6 | ✅ Complete | 2026-04-02 |
| 29 | v1.7 | ✅ Complete | 2026-04-02 |
| 30 | v1.7 | ✅ Complete | 2026-04-02 |
| 31 | v1.7 | ✅ Complete | 2026-04-03 |
| 32 | v1.7 | ✅ Complete | 2026-04-03 |
| 33 | v1.7 | ⬜ Pending | — |

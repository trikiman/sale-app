---
phase: 3
plan: 1
title: "Verify green scraper accuracy is already fixed"
wave: 1
depends_on: []
files_modified: []
requirements:
  - SCRP-07
autonomous: true
---

<objective>
Verify that the green scraper refactoring from conversation 27a0c0d3 (March 28) already satisfies SCRP-07:
"Green scraper captures ≥90% of items shown on live VkusVill green section."

The refactored scraper uses modal DOM extraction + basket API enrichment, which should capture 100% of items.
</objective>

<tasks>

<task id="3.1.1">
<title>Verify green scraper accuracy is already fixed</title>
<action>
Audit scrape_green_add.py and scrape_green_data.py to confirm:
1. Modal DOM scraping captures all items (scroll-to-load loop)
2. Merge logic combines modal + inline + basket data
3. No data loss paths remain
</action>
<acceptance_criteria>
- scrape_green_add.py saves green_modal_products.json with 100% modal items
- scrape_green_data.py merges modal + inline green section + basket API
- All items have name, price, and image from modal DOM extraction
- No regression paths where items could be dropped
</acceptance_criteria>
</task>

</tasks>

<verification>
Code audit confirms scraper accuracy fix is in place from prior refactoring.
</verification>

<must_haves>
- Confirm ≥90% capture rate architecture
- No new code needed — just verification
</must_haves>

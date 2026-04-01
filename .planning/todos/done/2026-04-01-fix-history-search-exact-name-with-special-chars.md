---
created: 2026-04-01T08:59:52Z
title: Fix history search - exact name copy-paste fails
area: api
files:
  - backend/main.py:3171-3173
  - database/sale_history.py:243-253
---

## Problem

Copying an exact product name from VkusVill.ru (e.g. `Салат "Цезарь" с курицей и пекинской капустой`) and pasting into history search returns zero results.

Likely causes:
1. **Non-breaking spaces (U+00A0 `\xa0`)** — VkusVill uses `\xa0` (nbsp) between words in product names, but copy-paste may produce regular spaces, or vice versa
2. **Unicode quote characters** — product names may use `"` (U+201C/U+201D curly quotes) vs `"` (U+0022 straight quotes) vs `«»` (guillemets)
3. **The `total_sale_count > 0` filter** — if searching finds the product but it has 0 sale count, the new filter excludes it (need to verify: does the search branch bypass this filter correctly?)

## Solution

1. Normalize both the search input and the DB name before comparison: replace `\xa0` with space, normalize quotes
2. Add `REPLACE(pc.name, char(160), ' ')` in the SQL query
3. Verify the search branch correctly bypasses the `total_sale_count > 0` filter (it should — the `else` clause only adds that filter when no search is present)

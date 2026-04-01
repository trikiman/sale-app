---
created: 2026-04-01T08:59:52Z
title: Fix history search - fuzzy matching for misspellings
area: api
files:
  - backend/main.py:3171-3173
  - miniapp/src/HistoryPage.jsx:192-204
---

## Problem

History search uses strict `LIKE` matching (`LOWER(pc.name) LIKE LOWER(?)`) which fails on Cyrillic misspellings. Example: searching "цезерь" (misspelled) finds nothing, while VkusVill.ru correctly resolves it to "Цезарь" products.

Users expect the same tolerance VkusVill has — common Cyrillic typos (е↔а, и↔ы) should still return relevant results.

## Solution

Options:
1. **SQLite FTS5** — create a full-text search index on product_catalog.name. Supports prefix matching, tokenization
2. **Trigram similarity** — split search into 3-char windows, match products scoring above threshold
3. **Character normalization** — map common Cyrillic confusables (е↔а, и↔ы, о↔а) and generate multiple LIKE queries
4. **Levenshtein distance** — SQLite extension or Python-side fuzzy matching on top N results

Recommended: FTS5 for best SQLite-native performance + fallback to LIKE for short queries.

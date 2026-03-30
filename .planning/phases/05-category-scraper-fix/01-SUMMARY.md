---
phase: 5
plan: 1
subsystem: category-scraper
tags: [scraper, categories, determinism]
key-files:
  modified:
    - scrape_categories.py
key-decisions:
  - "Changed from last-write-wins to first-write-wins for category assignment"
  - "Removed total_updated counter since existing categories are never overwritten"
requirements-completed: [SCRP-09]
duration: "2 min"
completed: "2026-03-30"
---

# Phase 5: Category Scraper Fix — Summary

## Root Cause
`scrape_categories.py` used **last-write-wins** for category assignment. Products appearing in multiple VkusVill categories got the LAST category from `asyncio.gather` results — whose order is non-deterministic.

## Fix
Changed to **first-write-wins**: `if pid not in db['products']` — only new products get assigned. Existing categories are never overwritten across runs.

## Commit
`16a092c` — fix(05-01): deterministic category assignment with first-write-wins

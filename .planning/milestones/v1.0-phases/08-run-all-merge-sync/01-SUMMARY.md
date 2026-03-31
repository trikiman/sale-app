---
one_liner: "Run All now runs scrapers sequentially then merges once after all complete"
---
# Phase 8 Summary
- BACK-01: Replaced 3 independent `background_tasks.add_task()` with single `run_all_with_merge()` that runs green→red→yellow sequentially, then merges if any succeeded

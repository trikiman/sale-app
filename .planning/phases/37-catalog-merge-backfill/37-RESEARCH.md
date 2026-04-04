# Phase 37: Catalog Merge & Backfill - Research

**Researched:** 2026-04-04
**Domain:** Dedupe merge from discovery source files into `category_db.json` and `product_catalog`
**Confidence:** HIGH

<research_summary>
## Summary

Phase 37 should stay additive and metadata-preserving. The existing local catalog already has richer taxonomy for older rows; the merge must not overwrite that with weaker overlay-source membership. New discovered products only need enough metadata to become searchable locally: stable `product_id`, `name`, and `image_url` when available.

The cleanest path is:
1. merge all Phase 36 source files into one deduped discovery artifact
2. update `category_db.json` additively from that artifact
3. extend `seed_product_catalog()` so discovery-backed fields like `image_url` flow into `product_catalog`
</research_summary>

<dont_hand_roll>
## Don't Hand-Roll

- Do not bypass `category_db.json` and write discovery rows straight into runtime search code.
- Do not let weaker discovery metadata overwrite richer existing taxonomy.
- Do not make Phase 37 depend on per-source raw files at runtime once the merged artifact exists.
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

- Overwriting good taxonomy with overlay-source labels
- Losing source provenance during dedupe
- Adding new rows to `category_db.json` but forgetting to flow `image_url` into `product_catalog`
</common_pitfalls>

<sources>
## Sources

- `.planning/phases/36-supplemental-catalog-discovery/36-VERIFICATION.md`
- `data/catalog_discovery_state.json`
- `database/sale_history.py`
- `scrape_merge.py`
- `utils.py`
</sources>

---

*Phase: 37-catalog-merge-backfill*
*Research completed: 2026-04-04*
